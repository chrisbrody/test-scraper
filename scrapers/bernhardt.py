"""
Bernhardt.com Product Scraper
Scrapes product data from Bernhardt category pages using Selenium for JS rendering and JSON-LD extraction.
"""

import json
import os
import re
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Handle both direct execution and module import
try:
    from .supabase_utils import sync_products_to_supabase
except ImportError:
    from supabase_utils import sync_products_to_supabase

# --- Configuration for User to Update ---
BASE_URL = "https://www.bernhardt.com"

# Category configuration with page ranges
# Format: {"url": "category_url", "pages": number_of_pages}
# Each page represents PAGE_SIZE (48) products, starting from page 1
CATEGORIES = [
    {
        "url": "https://www.bernhardt.com/products/luxury-bedroom-furniture",
        "pages": 2
    },
]

PAGE_SIZE = 48
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT_FILE = 'bernhardt_products.json'

# Selectors for finding product links on category pages
PRODUCT_LINK_SELECTOR = 'a[href^="/shop/"]'

# --- JSON-LD Specific Key Mapping (PRECISION FOR BERNHARDT.COM) ---
JSON_LD_MAPPING = {
    "Name": ["name"],
    "Img Url": ["image"],
    "Price": ["offers", "price"],
    "Sku": ["sku"],
    "In Stock?": ["offers", "availability"]
}

# Fallback Selectors (placeholders, for product *detail* page HTML if JSON-LD fails)
FALLBACK_NAME_SELECTOR = 'h1.product-detail-name'
FALLBACK_IMG_URL_SELECTOR = 'img.product-detail-image'
FALLBACK_PRICE_SELECTOR = 'span.product-detail-price'
FALLBACK_SKU_SELECTOR = 'span.product-detail-sku'
FALLBACK_STOCK_STATUS_SELECTOR = 'span.product-detail-stock'

# --- END Configuration ---


def create_driver():
    """Create and configure a Chrome WebDriver with headless options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    # Use Selenium Manager to auto-download correct ChromeDriver version
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def fetch_page_with_selenium(driver, url: str, wait_for_selector: str = None, force_reload: bool = False) -> Optional[str]:
    """
    Fetch a page using Selenium to render JavaScript

    Args:
        driver: Selenium WebDriver instance
        url: URL to fetch
        wait_for_selector: CSS selector to wait for before returning HTML
        force_reload: If True, force a hard refresh of the page

    Returns:
        Rendered HTML as string or None if failed
    """
    try:
        # Navigate to URL
        driver.get(url)

        # Force reload if requested (helps with Angular SPAs)
        if force_reload:
            time.sleep(1)
            driver.refresh()

        # Wait for Angular to load products
        if wait_for_selector:
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                )
            except:
                print(f"  Warning: Timeout waiting for selector '{wait_for_selector}'")

        # Additional wait for Angular to finish rendering
        time.sleep(5)

        return driver.page_source
    except Exception as e:
        print(f"  Error fetching page with Selenium: {e}")
        return None


def discover_product_urls(html: str, base_url: str) -> Set[str]:
    """
    Extract product URLs from a category page.

    Args:
        html: HTML content of category page
        base_url: Base URL for resolving relative links

    Returns:
        Set of absolute product URLs
    """
    soup = BeautifulSoup(html, 'html.parser')
    product_urls = set()

    # Find all product links using the selector
    product_links = soup.select(PRODUCT_LINK_SELECTOR)

    for link in product_links:
        href = link.get('href')
        if href:
            # Remove query parameters like ?position=-1
            clean_href = href.split('?')[0]
            absolute_url = urljoin(base_url, clean_href)
            product_urls.add(absolute_url)

    return product_urls


def discover_all_product_urls_selenium(driver, category_url: str, max_pages: int) -> Set[str]:
    """
    Discover all product URLs from a category by paginating through specified number of pages.

    Args:
        driver: Selenium WebDriver instance
        category_url: Starting category URL
        max_pages: Maximum number of pages to crawl for this category

    Returns:
        Set of all discovered product URLs
    """
    all_product_urls = set()

    print(f"\nDiscovering products from: {category_url}")
    print(f"  Max pages to crawl: {max_pages}")

    # Navigate to first page
    driver.get(category_url)
    time.sleep(3)

    # Wait for products to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.grid-item'))
        )
    except:
        print(f"  Warning: Timeout waiting for products to load")

    for page_num in range(1, max_pages + 1):
        print(f"  Scraping page {page_num}/{max_pages}")

        # Wait a bit for page to fully render
        time.sleep(3)

        # Get current page HTML
        html = driver.page_source

        # Extract product URLs from this page
        page_product_urls = discover_product_urls(html, BASE_URL)

        if not page_product_urls:
            print(f"  ⚠ No products found on page {page_num}")
            break

        products_found = len(page_product_urls)
        new_products = page_product_urls - all_product_urls
        all_product_urls.update(page_product_urls)
        print(f"  ✓ Found {products_found} products on page {page_num} ({len(new_products)} new)")

        # Debug: show first 3 SKUs on this page
        if page_product_urls:
            sample_urls = list(page_product_urls)[:3]
            print(f"  Sample URLs: {', '.join([url.split('/')[-1] for url in sample_urls])}")

        # If not the last page, navigate to the next page
        if page_num < max_pages:
            try:
                next_page = page_num + 1
                print(f"  Navigating to page {next_page}...")

                # Get the room type from the URL (e.g., "luxury-bedroom-furniture" -> "Bedroom")
                room_type = "Bedroom"  # This should be extracted from category_url
                if "dining" in category_url.lower():
                    room_type = "Dining"
                elif "living" in category_url.lower():
                    room_type = "Living"
                elif "office" in category_url.lower():
                    room_type = "Office"
                elif "outdoor" in category_url.lower():
                    room_type = "Outdoor"

                # Construct the hash URL format that Angular uses
                next_url = f"{category_url}#?RoomType={room_type}&$MultiView=Yes&orderBy={room_type}Position&context=shop&page={next_page}"
                print(f"  Next URL: {next_url}")

                driver.execute_script(f"window.location.href = '{next_url}';")

                # Wait for the new page to load
                time.sleep(5)

                # Wait for products to appear
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.grid-item'))
                )
            except Exception as e:
                print(f"  ⚠ Error navigating to next page: {e}")
                break

    print(f"  Total products discovered: {len(all_product_urls)}")
    return all_product_urls


def extract_data_from_json_ld(soup: BeautifulSoup, product_url: str) -> Optional[Dict]:
    """
    Extract product data from JSON-LD structured data.

    Args:
        soup: BeautifulSoup object of product page
        product_url: URL of the product page (for reference)

    Returns:
        Dictionary with extracted product data or None if extraction failed
    """
    try:
        # Find all JSON-LD scripts
        json_ld_scripts = soup.find_all('script', type='application/ld+json')

        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)

                # Check if this is a Product type JSON-LD
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    # Extract ALL fields (we'll filter what goes to DB later)
                    product_data = {
                        "product_url": product_url,
                        "name": data.get('name', ''),
                        "img_url": data.get('image', ''),
                        "price": data.get('offers', {}).get('price', ''),
                        "sku": data.get('sku', ''),
                        "in_stock": "http://schema.org/InStock" in data.get('offers', {}).get('availability', '')
                    }

                    # Validate that we got essential data
                    if product_data["name"] and product_data["sku"]:
                        return product_data

            except json.JSONDecodeError:
                continue

    except Exception as e:
        print(f"Error extracting JSON-LD from {product_url}: {e}")

    return None


def extract_data_from_html_fallback(soup: BeautifulSoup, product_url: str) -> Dict:
    """
    Fallback method to extract product data from HTML if JSON-LD fails.

    Args:
        soup: BeautifulSoup object of product page
        product_url: URL of the product page

    Returns:
        Dictionary with extracted product data (may contain empty values)
    """
    product_data = {
        "product_url": product_url,
        "name": "",
        "img_url": "",
        "sku": "",
    }

    try:
        # Try to extract name
        name_elem = soup.select_one(FALLBACK_NAME_SELECTOR)
        if name_elem:
            product_data["name"] = name_elem.get_text(strip=True)

        # Try to extract image
        img_elem = soup.select_one(FALLBACK_IMG_URL_SELECTOR)
        if img_elem:
            product_data["img_url"] = img_elem.get('src', '')

        # Try to extract SKU
        sku_elem = soup.select_one(FALLBACK_SKU_SELECTOR)
        if sku_elem:
            product_data["sku"] = sku_elem.get_text(strip=True)

    except Exception as e:
        print(f"Error in HTML fallback extraction for {product_url}: {e}")

    return product_data


def scrape_single_product_page_selenium(driver, url: str) -> Optional[Dict]:
    """
    Scrape a single product page using Selenium.

    Args:
        driver: Selenium WebDriver instance
        url: Product page URL

    Returns:
        Dictionary with product data or None if scraping failed
    """
    html = fetch_page_with_selenium(driver, url, wait_for_selector='script[type="application/ld+json"]')

    if not html:
        print(f"✗ Failed to fetch product page: {url}")
        return None

    soup = BeautifulSoup(html, 'html.parser')

    # Try JSON-LD extraction first
    product_data = extract_data_from_json_ld(soup, url)

    if product_data:
        print(f"✓ Scraped: {product_data.get('name', 'Unknown')}")
        return product_data

    # Fallback to HTML extraction
    print(f"⚠ JSON-LD not found for: {url}")
    product_data = extract_data_from_html_fallback(soup, url)

    if product_data and product_data.get("name"):
        print(f"✓ Scraped (HTML): {product_data.get('name', 'Unknown')}")
        return product_data

    print(f"✗ Failed to extract data: {url}")
    return None


def scrape(num_pages=None, max_products=None):
    """
    Main scraping function that matches the interface of other scrapers.

    Args:
        num_pages: Not used for Bernhardt (uses CATEGORIES config instead)
        max_products: Maximum number of products to scrape before stopping

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "bernhardt"

    print("=" * 80)
    print("Bernhardt.com Product Scraper")
    print("=" * 80)

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_product_urls = set()

    # Step 1: Use Selenium to discover product URLs from category pages
    print("\n" + "=" * 80)
    print("STEP 1: Discovering Product URLs (using Selenium)")
    print("=" * 80)

    driver = create_driver()

    try:
        for category in CATEGORIES:
            category_url = category["url"]
            max_pages = category["pages"]
            category_products = discover_all_product_urls_selenium(driver, category_url, max_pages)
            all_product_urls.update(category_products)

            # Check if we've hit max_products limit
            if max_products and len(all_product_urls) >= max_products:
                print(f"\n⚠ Reached max_products limit ({max_products}), stopping discovery")
                break
    finally:
        driver.quit()

    print(f"\n{'=' * 80}")
    print(f"Total unique products discovered: {len(all_product_urls)}")
    print("=" * 80)

    # Step 2: Scrape all product detail pages using Selenium
    print("\n" + "=" * 80)
    print("STEP 2: Scraping Product Details (using Selenium)")
    print("=" * 80)

    products = []
    driver = create_driver()

    try:
        # Convert set to list and limit by max_products if specified
        urls_to_scrape = list(all_product_urls)
        if max_products:
            urls_to_scrape = urls_to_scrape[:max_products]

        for idx, url in enumerate(urls_to_scrape, 1):
            print(f"[{idx}/{len(urls_to_scrape)}] Scraping: {url}")
            product_data = scrape_single_product_page_selenium(driver, url)
            if product_data:
                products.append(product_data)

            # Small delay to be respectful
            time.sleep(0.5)
    finally:
        driver.quit()

    # Step 3: Save to JSON file (backup)
    print("\n" + "=" * 80)
    print("STEP 3: Saving to JSON (backup)")
    print("=" * 80)

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    print(f"✓ Backup saved to: {output_path}")

    # Step 4: Sync to Supabase (filter to only DB fields)
    print("\n" + "=" * 80)
    print("STEP 4: Syncing to Supabase")
    print("=" * 80)

    # Filter products to only include fields that exist in DB schema
    db_products = []
    for product in products:
        db_product = {
            "name": product.get("name"),
            "sku": product.get("sku"),
            "img_url": product.get("img_url"),
            "product_url": product.get("product_url"),
        }
        db_products.append(db_product)

    stats = sync_products_to_supabase(db_products, vendor)

    # Add scraped count to stats
    stats["scraped_count"] = len(products)

    print("\n" + "=" * 80)
    print("Scraping Complete")
    print("=" * 80)

    return stats


if __name__ == "__main__":
    # When run directly, scrape all pages
    scrape()
