from utils import find_sitemap_url, get_all_sitemap_urls, get_leaf_sitemaps
from urllib.parse import urlparse, urljoin
from scraper import create_browser, close_browser, scrape_text, ddg_results2, google_results

# print(ddg_results2('contact number site:noto360.com'))

# print(get_leaf_sitemaps('https://noto360.com/sitemap.xml'))

print(google_results('contact number site:noto360.com'))