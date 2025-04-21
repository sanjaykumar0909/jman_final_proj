# Use Case:
To automate the process of extraction of company name's information from the internet via any source or method

# Project Instructions

## Setup

1. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

1. Activate the virtual environment:
   ```bash
   .venv\Scripts\activate
   ```

## Execution Steps

1. Run the script to fetch domains:
   ```bash
   python get_domains.py
   ```

2. Get data only using duckduckgo with the help of domains:
   ```bash
   python search-only-main.py
   ```

3. Gets sitemap for websites:
   ```bash
   python get_sitemaps.py
   ```

4. main script combines search logic, web crawling and RAG for data extraction:
   ```bash
   python main.py
   ```

## Challenges faced

* I'm using duckduckgo as my search engine as it permits scraping, but has lower accuracy than google or bing
* Details like finance cannot be found and require a third party (crunchbase, uk.gov.in) data provider which is either paid or free but less accuracy
* Most websites list their customers as image logos and not as text which is unable to scrape
* Free tier gemini models have low accuracy
