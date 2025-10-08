"""
Sherrill Furniture Product Scraper
Scrapes product data from Sherrill Furniture listing page using traditional HTML parsing.
All 513 products are on a single page when using items_per_page=All.
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
except ImportError:
    from supabase_utils import sync_products_to_supabase
    from proxy_utils import get_proxy_manager, add_delay

# --- Configuration ---
BASE_URL = "https://www.sherrillfurniture.com"
LISTING_URL = f"{BASE_URL}/search-results?items_per_page=All"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT_FILE = 'sherrillfurniture_products.json'

# Selectors for finding product items on listing page
PRODUCT_ITEM_SELECTOR = 'div.col-25._25-col-product-results'
PRODUCT_LINK_SELECTOR = 'a.product-results-tile'
PRODUCT_IMG_SELECTOR = 'img'
PRODUCT_SKU_SELECTOR = 'h3.product-number'
PRODUCT_NAME_SELECTOR = 'div.product-name'

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
        time.sleep(3)

        return driver.page_source
    except Exception as e:
        print(f"  Error fetching page with Selenium: {e}")
        return None


def extract_products_from_listing_page(html: str, base_url: str, seen_skus: Set[str]) -> List[Dict]:
    """
    Extract product data from the listing page HTML.

    Args:
        html: HTML content of listing page
        base_url: Base URL for resolving relative links
        seen_skus: Set of SKUs already encountered (for deduplication)

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

            # Extract SKU (format: "Model  4222-4U")
            sku_elem = item.select_one(PRODUCT_SKU_SELECTOR)
            sku = ''
            if sku_elem:
                sku_text = sku_elem.get_text(strip=True)
                # Remove "Model " prefix
                sku = sku_text.replace('Model', '').strip()

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
                img_url = urljoin(base_url, img_src) if img_src else ''

            # Only add if we have at least a SKU
            if sku:
                product_data = {
                    "name": name,
                    "sku": sku,
                    "img_url": img_url,
                    "product_url": product_url,
                    "price": None,  # No price available
                    "in_stock": None  # No stock status available
                }

                products.append(product_data)
                seen_skus.add(sku)
                print(f"  ✓ Found: {sku} - {name}")

        except Exception as e:
            print(f"  ✗ Error extracting product from item: {e}")
            continue

    return products


def scrape(num_pages=None, max_products=None):
    """
    Main scraping function that matches the interface of other scrapers.

    Args:
        num_pages: Not used for Sherrill Furniture (all products on one page)
        max_products: Maximum number of products to scrape before stopping

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "sherrillfurniture"

    print("=" * 80)
    print("Sherrill Furniture Product Scraper")
    print("=" * 80)
    print(f"Scraping all products from: {LISTING_URL}")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_products = []
    seen_skus = set()  # Track SKUs to prevent duplicates

    # Create Selenium driver
    driver = create_driver()

    try:
        print(f"\nFetching listing page...")
        html = fetch_page_with_selenium(driver, LISTING_URL, wait_for_selector=PRODUCT_ITEM_SELECTOR)

        if not html:
            print(f"  ✗ Failed to fetch listing page")
            return {
                "scraped_count": 0,
                "success_count": 0,
                "error_count": 0,
                "deleted_count": 0
            }

        print(f"Extracting products...")
        all_products = extract_products_from_listing_page(html, BASE_URL, seen_skus)

        # Apply max_products limit if specified
        if max_products and len(all_products) > max_products:
            print(f"\n⚠ Limiting to max_products ({max_products})")
            all_products = all_products[:max_products]

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
    # When run directly, scrape all products
    scrape()
