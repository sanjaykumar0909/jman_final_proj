from utils import find_sitemap_url
from openpyxl import load_workbook

start, end = 65, 185
# Load the workbook and select the active sheet
wb = load_workbook("company_list.xlsx")
sheet = wb.active

# Read cells from column B and store in a list
sites = [sheet[f'B{row}'].value for row in range(start, end + 1)]
for site in sites:
    if sheet[f'S{start}'].value not in ["None", None]:
        print(f'skipped {start}')
        start+=1
        continue
    sheet[f'S{start}'] = str(find_sitemap_url(site))
    print(f'Sitemap for {site} at {start}: {sheet[f'S{start}'].value}')
    start += 1
    wb.save("company_list.xlsx")

