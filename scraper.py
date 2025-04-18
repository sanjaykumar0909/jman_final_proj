from asyncio import timeout
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import random
import time
from urllib.parse import urlparse, urljoin

# Fingerprint profiles with user agent, platform, and viewport
fingerprints = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
        "platform": "Win32",
        "viewport": {"width": 1920, "height": 1080}
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        "platform": "MacIntel",
        "viewport": {"width": 1440, "height": 900}
    },
    {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64)...",
        "platform": "Linux x86_64",
        "viewport": {"width": 1366, "height": 768}
    }
]

def create_browser():
    playwright = sync_playwright().start()

    fingerprint = random.choice(fingerprints)

    browser = playwright.chromium.launch(headless=False, slow_mo=10)
    context = browser.new_context(
        user_agent=fingerprint["user_agent"],
        viewport={"width": 1920, "height": 1080},
        locale="en-GB",
        timezone_id="Europe/London"
    )
    page = context.new_page()

    # Set user-agent header explicitly (optional, context already sets it)
    page.set_extra_http_headers({
        "User-Agent": fingerprint["user_agent"]
    })

    # Spoof navigator.platform
    page.add_init_script(f"""
        Object.defineProperty(navigator, 'platform', {{
            get: () => '{fingerprint["platform"]}'
        }});
    """)

    # Hide WebDriver property
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    return playwright, browser, page

def close_browser(playwright, browser):
    browser.close()
    playwright.stop()

def scrape_text(page, url: str) -> str:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    visible_text = ""

    try:
        page.goto(url, timeout=20000, wait_until="networkidle")
        # page.wait_for_timeout(random.uniform(1, 2.5))  
        page.wait_for_selector("body", timeout=15000)  # Wait for content

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg", "meta", "head"]):
            tag.decompose()

        for hidden in soup.select("[style*='display:none'], [style*='visibility:hidden']"):
            hidden.decompose()

        text = soup.get_text(separator="\n", strip=True)
        visible_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

        if not visible_text:
            print(f"⚠️ No visible text found at: {url}")

    except PlaywrightTimeoutError:
        print(f"❌ Timeout while loading {url}")
    except Exception as e:
        print(f"⚠️ Error scraping {url}: {e}")

    return visible_text

def google_results(query, page) -> str:
    """
    Perform a Google search and return the top results as a string.

    Args:
        query (str): The search query.
        page: The Playwright page object.

    Returns:
        str: A string containing the top search results or an error message.
    """
    try:
        # Navigate to Google search page
        page.goto("https://www.google.com", timeout=100000)

        # Accept cookies if prompted
        if page.query_selector("button[aria-label='Accept all']"):
            page.click("button[aria-label='Accept all']")

        # Fill the search query and submit
        page.fill("input[name='q']", query)
        page.press("input[name='q']", "Enter")

        # Wait for search results
        page.wait_for_selector("div#search", timeout=100000)

        # Extract the top results
        results = page.query_selector_all("div#search .tF2Cxc")
        snippet_texts = '; '.join([result.inner_text().strip() for result in results[:2]])

        return snippet_texts if snippet_texts else "No results found"
    except PlaywrightTimeoutError:
        return "❌ Timeout waiting for results."
    except Exception as e:
        return f"❌ An error occurred: {str(e)}"
    
def ddg_results2(query, page):
    captcha_detected = False

    # Function to handle responses and check for CAPTCHA
    def check_for_captcha(response):
        nonlocal captcha_detected
        if response.status == 202:
            print("⚠️ CAPTCHA detected. Please solve it manually.")
            captcha_detected = True

    # Listen to all responses
    page.on("response", check_for_captcha)

    # Navigate to DuckDuckGo search page
    page.goto("https://html.duckduckgo.com/html/?kl=uk-en", timeout=10000)

    # If CAPTCHA was detected, wait for manual solving
    if captcha_detected:
        input("⏸️ CAPTCHA detected. Solve it and press ENTER to continue...")

    # Proceed with search
    page.fill("input[name='q']", query)
    page.wait_for_timeout(500)
    page.click("input[type='submit']")

    # Wait for search results
    try:
        if page.query_selector_all('.no-results'):
            return None
        page.wait_for_selector(".result__snippet", timeout=10000)
    except PlaywrightTimeoutError:
        print("❌ Timeout waiting for results.")
        return None

    # Extract results while skipping ads
    text_results = page.query_selector_all(".result:not(.result--ad) .result__snippet")
    text_results = '; '.join([r.inner_text().strip() for r in text_results[:2]])

    links = page.query_selector_all("a.result__a")
    links = [link.get_attribute("href") for link in links[:2]]
    page.wait_for_timeout(700)

    return set(links), text_results


def ddg_results(query, page):
    captcha_detected = False

    # Function to handle responses and check for CAPTCHA
    def check_for_captcha(response):
        nonlocal captcha_detected
        if response.status == 202:
            print("⚠️ CAPTCHA detected. Please solve it manually.")
            captcha_detected = True

    # Listen to all responses
    page.on("response", check_for_captcha)

    # Navigate to DuckDuckGo search page
    page.goto("https://html.duckduckgo.com/html/?kl=uk-en", timeout=10000)

    # If CAPTCHA was detected, wait for manual solving
    if captcha_detected:
        input("⏸️ CAPTCHA detected. Solve it and press ENTER to continue...")

    # Proceed with search
    page.fill("input[name='q']", query)
    time.sleep(0.5)
    page.click("input[type='submit']")

    # Wait for search results
    try:
        if page.query_selector_all('.no-results'):
            return "No results"
        page.wait_for_selector(".result__snippet", timeout=10000)
    except PlaywrightTimeoutError:
        print("❌ Timeout waiting for results.")
        return "❌ Timeout err"

    # Extract results while skipping ads
    results = page.query_selector_all(".result:not(.result--ad) .result__snippet")
    snippet_texts = '; '.join([r.inner_text().strip() for r in results[:2]])
    time.sleep(0.5)
    return snippet_texts

def scrape_internal_links(page, url: str):
    """
    Navigates to the page and extracts all internal links (as relative paths) from <a> tags.
    Returns a list of relative internal paths (e.g., /about, /careers).
    """
    internal_links = []

    try:
        # Navigate to the URL
        page.goto(url, timeout=20000, wait_until="networkidle")
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        base_domain = urlparse(url).netloc

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()

            # Skip anchors, javascript, or mailto links
            if href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
                continue

            # Resolve full URL and check if it's internal
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)

            if parsed_url.netloc == base_domain:
                path = parsed_url.path
                if path and path != "/":
                    internal_links.append(path)

    except Exception as e:
        print(f"⚠️ Error scraping internal links from {url}: {e}")

    return list(set(internal_links))  # remove duplicates

# def get_all_text_from_url(url: str) -> str:
#     """
#     Fetches all the text content from a given URL.

#     Args:
#         url (str): The URL to fetch the text from.

#     Returns:
#         str: The text content of the page or an error message.
#     """
#     try:
#         playwright, browser, page = create_browser()
#         page.goto(url, timeout=100000)

#         # Wait for the page to load completely
#         page.wait_for_load_state("load")

#         # Extract all text content from the page
#         page_text = page.inner_text("body")
#         return page_text
#     except PlaywrightTimeoutError:
#         return "❌ Timeout while loading the page."
#     except Exception as e:
#         return f"❌ An error occurred: {str(e)}"
#     finally:
#         close_browser(playwright, browser)

