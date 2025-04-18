import requests
from bs4 import BeautifulSoup
import utils
from openpyxl import load_workbook
import random
import time 

wb = load_workbook("company_list.xlsx")
sheet = wb["Sheet1"]
start = 120 # excel starting and ending row
end = 186

company_list = [str(cell.value).strip() for cell in sheet['A'] if cell.value][start-1: end]

for company in company_list:

    query = f'{company} official website'

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    # Use HTML version of DuckDuckGo
    params = {
        "q": query,
        "kl": "uk-en"
    }

    url = "https://html.duckduckgo.com/html/"  # lightweight, HTML-only endpoint

    response = requests.get(url, headers=headers, params=params)
    soup = BeautifulSoup(response.text, "html.parser")
    
    result = soup.find("a", class_="result__a")
    title = result.get_text()
    link = utils.extract_real_url(result.get("href"))
    
    pos = f'B{start}'
    start+=1
    sheet[pos] = link

    if start == end: 
        wb.save('company_list.xlsx')
        break

    time.sleep(random.uniform(2, 4))
        


