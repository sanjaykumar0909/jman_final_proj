import os
from dotenv import load_dotenv
import google.generativeai as genai
from openpyxl import load_workbook
import utils
import scraper
import tldextract

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name="models/gemini-2.0-flash-lite")
# model = genai.GenerativeModel(model_name="models/gemini-1.5-pro")
chat = model.start_chat()

wb = load_workbook("company_list.xlsx")
sheet = wb["Sheet1"]

start, end = 162, 185
company_websites = [str(cell.value).strip() for cell in sheet['B'] if cell.value][start-1: end]
company_names = [str(cell.value).strip() for cell in sheet['A'] if cell.value][start-1: end]

playwright, browser, page = scraper.create_browser()

for name, site in zip(company_names, company_websites):
    extracted = tldextract.extract(site)
    if 'eu' in extracted.registered_domain:
        base_domain = f'{extracted.subdomain}.{extracted.registered_domain}'
    else:
        base_domain = f"{extracted.domain}.{extracted.suffix}"

#     query = f'about us site:{base_domain}' # C
#     description_context = scraper.ddg_results(query, page)
#     prompt = f"""
# give a brief description from the following context:
# {description_context}
# """
#     description = model.generate_content(prompt)
#     sheet[f'C{start}'] = description.text
    
    res = chat.send_message('For the following prompts just answer to the point, if answer not found give "Not found"')

    query = f'industry site:{base_domain}' # F
    query2 = f'{name} industry'
    industry_context = scraper.ddg_results(query, page)
    industry_context += scraper.ddg_results(query2, page)
    prompt = f"""
In which industry or sector does company "{name}" in, from following context:
{industry_context}
"""
    industry = chat.send_message(prompt)
    chat.history.pop();chat.history.pop()
    sheet[f'F{start}'] = industry.text


    query = f'total employees staffs count {name} site:{base_domain}' # H
    query2 = f'{name} total employees'
    employee_context = scraper.ddg_results(query, page)
    employee_context += scraper.ddg_results(query2, page)
    prompt = f"""
Total employees count of company "{name}" from the context:
{employee_context}
"""
    employee_count = chat.send_message(prompt)
    chat.history.pop();chat.history.pop()
    sheet[f'H{start}'] = employee_count.text
    
    
    query = f'geography location site:{base_domain}' # J
    geography_context = scraper.ddg_results(query, page)
    prompt = f"""
Geography of company "{name}" from following context:
{geography_context}
"""
    geography = chat.send_message(prompt)
    chat.history.pop();chat.history.pop()
    sheet[f'J{start}'] = geography.text


    query = f'parent company site:{base_domain}' # K
    query2 = f'{sheet[f"A{start}"].value} parent company'
    parent_cmp_context = scraper.ddg_results(query, page)
    parent_cmp_context += scraper.ddg_results(query2, page)
    prompt = f"""
Parent company of "{name}" from following context:
{parent_cmp_context}
"""
    parent_cmp = chat.send_message(prompt)
    chat.history.pop();chat.history.pop()
    sheet[f'K{start}'] = parent_cmp.text


    query = f'address location site:{base_domain}' # all address related fields
    query2 = f'{sheet[f"A{start}"].value} address'
    address_context = scraper.ddg_results(query, page)
    address_context += scraper.ddg_results(query2, page)
    prompt= f"""
Give address in the following JSON structure {{
"street" : [],
"zip/postal" : [],
"city" : [],
"country/region" : []
}}
from the context:
{address_context}
"""
    address = model.generate_content(prompt)
    address = utils.clean_load_json(address.text)
    if address is None:
        address = {
            "street": "Not found",
            "zip/postal": "Not found",
            "city": "Not found",
            "country/region": "Not found"
        }
    sheet[f'L{start}'] = str(address.get("street", "Not found"))
    sheet[f'M{start}'] = str(address.get("zip/postal", "Not found"))
    sheet[f'N{start}'] = str(address.get("city", "Not found"))
    sheet[f'O{start}'] = str(address.get("country/region", "Not found"))


#     query = f'email site:{base_domain}' # K
#     query2 = f'{sheet[f'A{start}'].value} email'
#     email_context = scraper.ddg_results(query, page)
#     email_context += scraper.ddg_results(query2, page)
#     prompt = f"""
# Email of "{name}" from following context:
# {email_context}
# """
#     email = chat.send_message(prompt)
#     chat.history.pop();chat.history.pop()
#     sheet[f'Q{start}'] = email.text
    

#     query = f'Contact phone number site:{base_domain}' # K
#     query2 = f'{sheet[f"A{start}"].value} contact phone number'
#     number_context = scraper.ddg_results(query, page)
#     number_context += scraper.ddg_results(query2, page)
#     prompt = f"""
# Contact number of "{name}" from following context:
# {number_context}
# """
#     number = chat.send_message(prompt)
#     chat.history.pop();chat.history.pop()
#     sheet[f'R{start}'] = number.text
    
    start += 1
    chat.history.clear()
    print(f"Processed {name} ({start-1})")
    wb.save("company_list.xlsx")


scraper.close_browser(playwright, browser)

