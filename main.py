import json
import os
from dotenv import load_dotenv
import numpy as np
import google.generativeai as genai
from google.generativeai import embedding
from openpyxl import load_workbook
from utils import get_all_sitemap_urls, get_leaf_sitemaps, clean_load_json, extract_paths_from_csv, is_valid_path
from typing import List
import faiss
from scraper import create_browser, close_browser, scrape_text, ddg_results2, scrape_internal_links
import tldextract
from urllib.parse import urljoin, urlparse

os.makedirs("embeddings", exist_ok=True)

def chunk_text(text: str, max_chars: int = 360) -> List[str]:
    """
    Splits the input text into chunks of max_chars characters.
    It tries to split at the nearest space to avoid cutting words.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            # Try to split at the nearest space before max_chars
            space_index = text.rfind(" ", start, end)
            if space_index != -1:
                end = space_index
        chunks.append(text[start:end].strip())
        start = end
    return chunks

def load_and_store_faiss(chunks: list[str], output_path: str):
    """
    Embeds each chunk using Google Generative AI and writes the FAISS index to disk.

    Args:
        chunks (list[str]): List of text chunks.
        output_path (str): Path where the .index file should be saved.
    """
    if not chunks:
        raise ValueError("Chunks list is empty.")

    # Embed each chunk
    embeddings = [
        embedding.embed_content(
            model="models/text-embedding-004",
            content=chunk,
            task_type="retrieval_document"
        )["embedding"]
        for chunk in chunks
    ]

    # Convert to numpy float32 array
    embedding_array = np.array(embeddings, dtype="float32")

    # Initialize FAISS index
    dim = embedding_array.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embedding_array)

    # Save index to file
    faiss.write_index(index, output_path)
    print(f"✅ FAISS index saved to: {output_path}")
    return index


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")


genai.configure(api_key=api_key)
m20 = genai.GenerativeModel(model_name="models/gemini-2.0-flash")
m20l = genai.GenerativeModel(model_name="models/gemini-2.0-flash-lite")
m15 = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

wb = load_workbook("company_list.xlsx")
sheet = wb["Sheet1"]

start, end = 186, 186
# company_websites = [str(cell.value).strip() for cell in sheet['B'] if cell.value][start-1: end]
# company_names = [str(cell.value).strip() for cell in sheet['A'] if cell.value][start-1: end]

playwright, browser, page = create_browser()

for row in range(start, end+1):
        
    extracted = tldextract.extract(sheet[f'B{row}'].value)
    if 'eu' in extracted.registered_domain:
        base_domain = f'{extracted.subdomain}.{extracted.registered_domain}'
    else:
        base_domain = f"{extracted.domain}.{extracted.suffix}"

    chat = m20l.start_chat()
    chat.send_message('For the following prompts just answer to the point, if answer not found give "Not found"')
    cmp_name = sheet[f'A{row}'].value
    ddg_links = set()


    query = f'industry site:{base_domain}' # F
    query2 = f'{cmp_name} company industry'
    # links, industry_context = ddg_results2(query, page)
    industry_context = ""
    ddg_res = ddg_results2(query, page)
    if ddg_res:
        links, industry_context = ddg_res
        ddg_links.update(links)
        links, r2 = ddg_results2(query2, page)
        ddg_links.update(links)
        industry_context +=' \n '+ r2


    query = f'total employees staffs count {cmp_name} site:{base_domain}'  # H
    query2 = f'{cmp_name} company employee count'
    employee_context = ""
    ddg_res = ddg_results2(query, page)
    if ddg_res:
        links, employee_context = ddg_res
        ddg_links.update(links)
        ddg_res2 = ddg_results2(query2, page)
        if ddg_res2:
            links, r2 = ddg_res2
            ddg_links.update(links)
            employee_context += ' \n ' + r2

    # Parent Company
    query = f'parent company site:{base_domain}'  # K
    query2 = f'{cmp_name} parent company'
    parent_cmp_context = ""
    ddg_res = ddg_results2(query, page)
    if ddg_res:
        links, parent_cmp_context = ddg_res
        ddg_links.update(links)
        ddg_res2 = ddg_results2(query2, page)
        if ddg_res2:
            links, r2 = ddg_res2
            ddg_links.update(links)
            parent_cmp_context += ' \n ' + r2

    # Address or Location
    query = f'address location site:{base_domain}'
    query2 = f'{cmp_name} company address'
    address_context = ""
    ddg_res = ddg_results2(query, page)
    if ddg_res:
        links, address_context = ddg_res
        ddg_links.update(links)
        ddg_res2 = ddg_results2(query2, page)
        if ddg_res2:
            links, r2 = ddg_res2
            ddg_links.update(links)
            address_context += ' \n ' + r2
    chat.history.clear()
    ddg_links = set(map(lambda x: urlparse(x.strip()).path, ddg_links))

    leaf_sitemaps = get_leaf_sitemaps(sheet[f'S{row}'].value)
    leaf_sitemaps = list(map(lambda x: urlparse(x.strip()).path, leaf_sitemaps))
    if len(leaf_sitemaps) > 1:
        print('company has multiple sitemaps')
        paths = "\n".join(leaf_sitemaps)
        prompt = f"""
        To answer these questions, what are all the sitemap urls would you require:
        1. Software classification of company
        2. Is company "enterprise grade" or "SMB"
        3. Industry of company
        4. Customer/client name list
        5. Employee head count
        6. Investors list
        7. Geography
        8. Parent company
        9. Address of company
        10. Finance 
        11. Email
        12. Phone number

        Available URLs:
        {paths}

        If english URLs available, don't pick other language URLs.
        If no relevant sitemaps found return just the homepage URL "/".
        Generate ONLY the URLs as comma separated values, don't generate any other extra explanations or texts
        """
        required_paths = m20.generate_content(prompt).text
        required_paths = extract_paths_from_csv(required_paths)
    else:
        print('company has single sitemap')
        required_paths = leaf_sitemaps

    sitemap_failed = False
    if (sheet[f'S{row}'].value is None or sheet[f'S{row}'].value.strip() == "None") \
    or (len(required_paths)==0 or not is_valid_path(required_paths[0]) or required_paths[0].strip() == "/"):
        sitemap_failed = True
        print('sitemap failed')

    else:
        print('getting sitemap urls')
        paths = []
        for path in required_paths:
            paths.append(get_all_sitemap_urls('https://'+ base_domain +path))
        
        paths = [item for sublist in paths for item in sublist]
        paths = "\n".join(paths)

        prompt = f"""
        To answer these questions, what are all the URLs would you require:
        1. Software classification of company
        2. Is company "enterprise grade" or "SMB"
        3. Industry of company
        4. Customer/client name list
        5. Employee head count
        6. Investors list
        7. Geography
        8. Parent company
        9. Address of company
        10. Finance 
        11. Email
        12. Phone number

        Available URLs:
        {paths}

        If english URLs available, don't pick other language URLs.
        If no relevant URLs found return just the homepage URL "/".
        Generate ONLY the URLs as comma separated values, don't generate any other extra explanations or texts
        """
        required_paths = m20.generate_content(prompt).text
        required_paths = extract_paths_from_csv(required_paths)
        if len(required_paths)==0 or not is_valid_path(required_paths[0]) or required_paths[0].strip() == "/":
            sitemap_failed = True
            print('no useful urls found')

        else:
            print('scraping siemaps')
            required_paths = set(required_paths) | ddg_links
            required_paths = set(map(lambda x: x.rstrip('/'), required_paths))
            
            scraped_text= []
            try :
                if '/' not in required_paths:
                    text = scrape_text(page, f'https://{base_domain}/')
                    scraped_text.append(text)
            except Exception as e:
                print(f"Error scraping homepage: {e}")

            for path in required_paths:
                if path:
                    try:
                        url = urljoin('https://'+ base_domain, path)
                        text = scrape_text(page, url)
                        print(f'for the url {url} the extraction is {len(text)}')
                        scraped_text.append(text)
                    except Exception as e:
                        print(f"Error scraping {path}: {e}")
    
    if sitemap_failed:
        paths = scrape_internal_links(page, f'https://{base_domain}/')
        paths = "\n".join(paths)
        prompt = f"""
        To answer these questions, what are all the URLs would you require:
        1. Software classification of company
        2. Is company "enterprise grade"  or "SMB"
        3. Industry of company
        4. Customer/client name list
        5. Employee head count
        6. Investors list
        7. Geography
        8. Parent company
        9. Address of company
        10. Finance 
        11. Email
        12. Phone number

        Available URLs:
        {paths}

        If english URLs available, don't pick other language URLs.
        If no relevant URLs found return just the homepage URL "/".
        Generate ONLY the URLs as comma separated values, don't generate any other extra explanations or texts
        """
        required_paths = m20.generate_content(prompt).text
        required_paths = extract_paths_from_csv(required_paths)
        required_paths = set(required_paths) | ddg_links
        required_paths = set(map(lambda x: x.rstrip('/'), required_paths))

        scraped_text= []
        for path in required_paths:
            try:
                url = urljoin('https://'+ base_domain, path)
                text = scrape_text(page, url)
                print(f'for the url {url} the extraction is {len(text)}')
                scraped_text.append(text)
            except Exception as e:
                print(f"Error scraping {path}: {e}")
        
        scraped_text = "\n".join(scraped_text)

    chunks = chunk_text(" ".join(scraped_text))
    with open(f'generated/chunks_cmp_{row}.json', 'w', encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=4)
        
    index = load_and_store_faiss(chunks, f'embeddings/cmp_{row}.index')

    questions = [
        "Software classification of company",
        "Is the company 'enterprise grade' or 'SMB'",
        "Industry of company",
        "Customer/client name list",
        "Employee or staff head count",
        "Investors list",
        "Geography",
        "Parent company",
        "Full address or location of company",
        "Finance details",
        "Email of company",
        "Phone number of company"
    ]

    # This will hold all retrieved chunks across questions
    context = ""

    for question in questions:
        try:
            # Embed the question
            query_embedding = embedding.embed_content(
                model="models/text-embedding-004",
                content=question
            )["embedding"]

            # Search top k chunks
            k = 3
            D, I = index.search(np.array([query_embedding], dtype="float32"), k=k)

            # Add the top chunks to the context
            retrieved_chunks = "\n\n".join([chunks[i] for i in I[0]])
            context += f"\n\n=== context for: {question} ===\n\n{retrieved_chunks}"

        except Exception as e:
            print(f"Error with question '{question}': {e}")

    # Optional: Write context to a file for inspection
    with open(f"generated/retrieved_chunks_{row}", "w", encoding="utf-8") as f:
        f.write(context)


    prompt = f"""
    You are a data extraction model. You have to extract the following information from the context provided.
    Generate the answer in JSON format given below, give "null" for the values you don't know, and don't generate any other extra explanations or texts:

    software_classification: <string>
    is_enterprise_grade: <string>
    industry: <string>
    customer_name_list: <list>
    employee_head_count: <number>
    investors_list: <list>
    geography: <string>
    parent_company: <string>
    street: <string>
    postal/zip_code: <string>
    city: <string>
    country/region: <string>
    finance: <string>
    email: <string>
    phone_number: <string>

    CONTEXT:
    {industry_context}\n
    {employee_context}\n
    {parent_cmp_context}\n
    {address_context}\n
    {context}
    """
    cmp_details = m20l.generate_content(prompt)
    cmp_details = clean_load_json(cmp_details.text)

    if cmp_details:
        cond = lambda x: x.value is None or x.value.strip() in ("None", "[]", "Not found")

        if cond(sheet[f'D{row}']):
            sheet[f'D{row}'].value = cmp_details.get('software_classification', None)
        if cond(sheet[f'E{row}']):
            sheet[f'E{row}'].value = cmp_details.get('is_enterprise_grade', None)
        if cond(sheet[f'F{row}']):
            sheet[f'F{row}'].value = cmp_details.get('industry', None)
        if cond(sheet[f'G{row}']):
            sheet[f'G{row}'].value = str(cmp_details.get('customer_name_list', None))
        if cond(sheet[f'H{row}']):
            sheet[f'H{row}'].value = cmp_details.get('employee_head_count', None)
        if cond(sheet[f'I{row}']):
            sheet[f'I{row}'].value = str(cmp_details.get('investors_list', None))
        if cond(sheet[f'J{row}']):
            sheet[f'J{row}'].value = cmp_details.get('geography', None)
        if cond(sheet[f'K{row}']):
            sheet[f'K{row}'].value = cmp_details.get('parent_company', None)
        if cond(sheet[f'L{row}']):
            sheet[f'L{row}'].value = cmp_details.get('street', None)
        if cond(sheet[f'M{row}']):
            sheet[f'M{row}'].value = cmp_details.get('postal/zip_code', None)
        if cond(sheet[f'N{row}']):
            sheet[f'N{row}'].value = cmp_details.get('city', None)
        if cond(sheet[f'O{row}']):
            sheet[f'O{row}'].value = cmp_details.get('country/region', None)
        if cond(sheet[f'P{row}']):
            sheet[f'P{row}'].value = cmp_details.get('finance', None)
        if cond(sheet[f'Q{row}']):
            sheet[f'Q{row}'].value = cmp_details.get('email', None)
        if cond(sheet[f'R{row}']):
            sheet[f'R{row}'].value = cmp_details.get('phone_number', None)
        wb.save("company_list.xlsx")
    else:
        print(f"No valid JSON received for row {row}.")
    print(f'\nRow {row} processed')
    
close_browser(playwright, browser)
    
