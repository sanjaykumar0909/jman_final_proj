from urllib.parse import urlparse, parse_qs, unquote, urljoin
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import random
import re
import json
import time
import tldextract
import cloudscraper
import xml.etree.ElementTree as ET

def extract_real_url(ddg_redirect_url):
    parsed = urlparse(ddg_redirect_url)
    qs = parse_qs(parsed.query)
    return unquote(qs.get("uddg", [""])[0])

def extract_paths_from_csv(path_string: str) -> list[str]:
    return [path.strip() for path in path_string.strip().split(",") if path.strip()]

def ddg_results2(query):
    params = {
        "q": query,
        "kl": "uk-en"
    }
    url = "https://html.duckduckgo.com/html/"  # lightweight, HTML-only endpoint
    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        ])
    }
    response = requests.get(url, headers=headers, params=params)
    time.sleep(random.uniform(1, 3.5)) 

    soup = BeautifulSoup(response.text, "html.parser")

    snippets = soup.find_all("a", class_="result__snippet", limit=2)
    snippet_texts = '; '.join([snippet.get_text(strip=True) for snippet in snippets])
    return snippet_texts
    
def clean_load_json(response_text: str):
    """
    Cleans and loads a JSON string from Gemini response text.
    
    Args:
        response_text (str): The raw text returned by Gemini.
        
    Returns:
        dict or None: Parsed JSON dictionary if successful, else None.
    """
    # Try to extract JSON from Markdown-style code block
    match = re.search(r"```(?:json)?\s*({.*?})\s*```", response_text, re.DOTALL)
    if match:
        json_text = match.group(1)
    else:
        # Fallback: Try to extract the first valid-looking JSON object
        match = re.search(r"({.*})", response_text, re.DOTALL)
        json_text = match.group(1) if match else None

    # Try parsing
    if json_text:
        try: 
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            print("JSON decode error:", e)
            return None
    else:
        print("No JSON found in response.")
        return None

def find_sitemap_url(url: str) -> str | None:
    """
    Attempts to locate the sitemap URL for a given website using cloudscraper.
    1. Tries checking both the www and non-www versions
    2. Checks robots.txt for a Sitemap entry
    3. Falls back to checking /sitemap.xml at root
    Returns the sitemap URL if found, else None
    """
    scraper = cloudscraper.create_scraper()

    def try_fetch_sitemap(base_url: str) -> str | None:
        base_url = base_url.rstrip("/")
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            response = scraper.get(robots_url, timeout=5)
            if response.status_code == 200:
                sitemap_matches = re.findall(r"Sitemap:\s*(\S+)", response.text, re.IGNORECASE)
                if sitemap_matches:
                    return sitemap_matches[0]
        except Exception:
            pass

        # Try fallback /sitemap.xml
        fallback_sitemap = urljoin(base_url, "/sitemap.xml")
        try:
            res = scraper.get(fallback_sitemap, timeout=5)
            if res.status_code == 200 and 'xml' in res.headers.get('Content-Type', ''):
                return fallback_sitemap
        except Exception:
            pass

        return None

    # Extract base domain
    extracted = tldextract.extract(url)
    registered = f"{extracted.domain}.{extracted.suffix}"

    variants = [
        f"https://{registered}",
        f"https://www.{registered}"
    ]

    for variant in variants:
        sitemap_url = try_fetch_sitemap(variant)
        if sitemap_url:
            return sitemap_url

    return None

def get_all_sitemap_urls(sitemap_url: str) -> list[str]:
    """
    Returns a flat list of all URL strings found.
    """
    scraper = cloudscraper.create_scraper()
    all_urls = []

    def parse_sitemap(url: str):
        try:
            res = scraper.get(url, timeout=10)
            if res.status_code != 200:
                print(f"❌ Failed to fetch {url}")
                return

            root = ET.fromstring(res.text)

            if root.tag.endswith("sitemapindex"):
                # Sitemap index: contains nested <sitemap> entries
                for sitemap in root.findall(".//{*}sitemap/{*}loc"):
                    child_sitemap_url = sitemap.text.strip()
                    parse_sitemap(child_sitemap_url)
            elif root.tag.endswith("urlset"):
                # Regular sitemap: contains <url> entries
                for url_tag in root.findall(".//{*}url/{*}loc"):
                    path = urlparse(url_tag.text.strip()).path
                    
                    if (len([segment for segment in path.strip("/").split("/") if segment]) <=2):
                        all_urls.append(path)
            else:
                print(f"⚠️ Unknown XML root tag in {url}: {root.tag}")

        except Exception as e:
            print(f"⚠️ Error parsing {url}: {e}")

    parse_sitemap(sitemap_url)
    # print(f'\n\n count: {len(all_urls)}')
    return all_urls




def get_leaf_sitemaps(sitemap_url: str) -> list[str]:
    """
    Recursively fetches only the leaf sitemap URLs (sitemaps that contain <url> tags)
    from a sitemap index and nested sitemaps.
    """
    scraper = cloudscraper.create_scraper()
    leaf_sitemaps = []

    def parse_sitemap(url: str):
        try:
            res = scraper.get(url, timeout=10)
            if res.status_code != 200:
                print(f"❌ Failed to fetch {url}")
                return

            root = ET.fromstring(res.text)

            if root.tag.endswith("sitemapindex"):
                # Contains nested sitemaps
                for sitemap in root.findall(".//{*}sitemap/{*}loc"):
                    child_sitemap_url = sitemap.text.strip()
                    parse_sitemap(child_sitemap_url)

            elif root.tag.endswith("urlset"):
                # This is a leaf sitemap (contains actual URLs)
                leaf_sitemaps.append(url)

            else:
                print(f"⚠️ Unknown XML root tag in {url}: {root.tag}")

        except Exception as e:
            print(f"⚠️ Error parsing {url}: {e}")

    parse_sitemap(sitemap_url)
    return leaf_sitemaps


def is_valid_path(path: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z0-9/_\-\.]+", path))