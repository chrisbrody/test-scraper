"""
Hickory Chair Product Scraper
Scrapes product data from Hickory Chair listing pages using traditional HTML parsing.
No pagination needed - single page per TypeID.
"""

import json
import os
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Handle both direct execution and module import
try:
    from .supabase_utils import sync_products_to_supabase
    from .proxy_utils import get_proxy_manager, add_delay
    from .categorization_utils import categorize_product
except ImportError:
    from supabase_utils import sync_products_to_supabase
    from proxy_utils import get_proxy_manager, add_delay
    from categorization_utils import categorize_product

# --- Configuration ---
BASE_URL = "https://www.hickorychair.com"

# TypeIDs to scrape - User should update this array
TYPE_IDS = [ 
    14,48,79, 
    # Add more TypeIDs here as needed
]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT_FILE = 'hickorychair_products.json'

# Selectors for finding product items on listing pages
PRODUCT_ITEM_SELECTOR = 'div.search-item'
PRODUCT_LINK_SELECTOR = 'a'
PRODUCT_IMG_SELECTOR = 'img'
PRODUCT_SKU_SELECTOR = 'div.search-item-sku'
PRODUCT_NAME_SELECTOR = 'div.search-item-name'

# --- END Configuration ---


def create_driver():
    """Create and configure a Chrome WebDriver with headless options and proxy support"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    # Configure proxy if enabled
    proxy_manager = get_proxy_manager()
    chrome_options = proxy_manager.configure_selenium_options(chrome_options)

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def fetch_page_with_selenium(driver, url: str, wait_for_selector: str = None) -> Optional[str]:
    """
    Fetch a page using Selenium to render JavaScript

    Args:
        driver: Selenium WebDriver instance
        url: URL to fetch
        wait_for_selector: CSS selector to wait for before returning HTML

    Returns:
        Rendered HTML as string or None if failed
    """
    try:
        driver.get(url)

        # Wait for products to load if selector provided
        if wait_for_selector:
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                )
            except:
                print(f"  Warning: Timeout waiting for selector '{wait_for_selector}'")

        # Additional wait for any JS rendering
        time.sleep(2)

        return driver.page_source
    except Exception as e:
        print(f"  Error fetching page with Selenium: {e}")
        return None


def extract_products_from_listing_page(html: str, base_url: str, seen_skus: Set[str], category_url: str = None) -> List[Dict]:
    """
    Extract product data from a listing page HTML.

    Args:
        html: HTML content of listing page
        base_url: Base URL for resolving relative links
        seen_skus: Set of SKUs already encountered (for deduplication)
        category_url: Category URL for room type extraction (optional)

    Returns:
        List of product dictionaries
    """
    soup = BeautifulSoup(html, 'html.parser')
    products = []

    # Find all product items
    product_items = soup.select(PRODUCT_ITEM_SELECTOR)

    for item in product_items:
        try:
            # Extract product link
            link_elem = item.select_one(PRODUCT_LINK_SELECTOR)
            if not link_elem:
                continue

            product_url = urljoin(base_url, link_elem.get('href', ''))

            # Extract SKU
            sku_elem = item.select_one(PRODUCT_SKU_SELECTOR)
            sku = sku_elem.get_text(strip=True) if sku_elem else ''

            # Skip if we've already seen this SKU
            if sku in seen_skus:
                print(f"  ⚠ Skipping duplicate SKU: {sku}")
                continue

            # Extract name
            name_elem = item.select_one(PRODUCT_NAME_SELECTOR)
            name = name_elem.get_text(strip=True) if name_elem else ''

            # Extract image
            img_elem = item.select_one(PRODUCT_IMG_SELECTOR)
            img_url = ''
            if img_elem:
                img_src = img_elem.get('src', '')
                img_url = urljoin(base_url, img_src)
                # Also check alt attribute for name if name is empty
                if not name:
                    name = img_elem.get('alt', '')

            # Only add if we have at least a SKU
            if sku:
                # Categorize product
                categorization = categorize_product(name, category_url)

                product_data = {
                    "name": name,
                    "sku": sku,
                    "img_url": img_url,
                    "product_url": product_url,
                    "price": None,  # No price available
                    "in_stock": None,  # No stock status available
                    "room_types": categorization['room_types'],
                    "product_type": categorization['product_type']
                }

                products.append(product_data)
                seen_skus.add(sku)
                print(f"  ✓ Found: {sku} - {name}")

        except Exception as e:
            print(f"  ✗ Error extracting product from item: {e}")
            continue

    return products


def scrape_type_id(driver, type_id: int, seen_skus: Set[str]) -> List[Dict]:
    """
    Scrape all products from a single TypeID listing page.

    Args:
        driver: Selenium WebDriver instance
        type_id: TypeID to scrape
        seen_skus: Set of SKUs already encountered (for deduplication)

    Returns:
        List of product dictionaries
    """
    url = f"{BASE_URL}/Products/ShowResults?TypeID={type_id}"
    print(f"\nScraping TypeID {type_id}: {url}")

    html = fetch_page_with_selenium(driver, url, wait_for_selector=PRODUCT_ITEM_SELECTOR)

    if not html:
        print(f"  ✗ Failed to fetch page for TypeID {type_id}")
        return []

    products = extract_products_from_listing_page(html, BASE_URL, seen_skus, url)
    print(f"  Total products from TypeID {type_id}: {len(products)}")

    return products


def scrape(num_pages=None, max_products=None):
    """
    Main scraping function that matches the interface of other scrapers.

    Args:
        num_pages: Not used for Hickory Chair (scrapes all TypeIDs)
        max_products: Maximum number of products to scrape before stopping

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "hickorychair"

    print("=" * 80)
    print("Hickory Chair Product Scraper")
    print("=" * 80)
    print(f"Scraping {len(TYPE_IDS)} TypeIDs: {TYPE_IDS}")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_products = []
    seen_skus = set()  # Track SKUs to prevent duplicates

    # Create Selenium driver
    driver = create_driver()

    try:
        for type_id in TYPE_IDS:
            type_products = scrape_type_id(driver, type_id, seen_skus)
            all_products.extend(type_products)

            # Check if we've hit max_products limit
            if max_products and len(all_products) >= max_products:
                print(f"\n⚠ Reached max_products limit ({max_products}), stopping")
                all_products = all_products[:max_products]
                break

    finally:
        driver.quit()

    print(f"\n{'=' * 80}")
    print(f"Total unique products scraped: {len(all_products)}")
    print(f"Total unique SKUs: {len(seen_skus)}")
    print("=" * 80)

    # Save to JSON file (backup)
    print("\nSaving to JSON (backup)")
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    print(f"✓ Backup saved to: {output_path}")

    # Sync to Supabase
    print("\n" + "=" * 80)
    print("Syncing to Supabase")
    print("=" * 80)

    stats = sync_products_to_supabase(all_products, vendor)

    # Add scraped count to stats
    stats["scraped_count"] = len(all_products)

    print("\n" + "=" * 80)
    print("Scraping Complete")
    print("=" * 80)

    return stats


if __name__ == "__main__":
    # When run directly, scrape all TypeIDs
    scrape()
