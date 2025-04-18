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

2. Get data only using duckduckgo:
   ```bash
   python search-only-main.py
   ```

3. Gets sitemap for websites:
   ```bash
   python get_sitemaps.py
   ```

4. main script combines search logic, web crawling and RAG:
   ```bash
   python main.py
   ```
