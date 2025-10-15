"""
Hickory Chair Product Scraper
Scrapes product data from Hickory Chair listing pages using traditional HTML parsing.
No pagination needed - single page per TypeID.


Living Room Ids
Sofa & loveseats-79
settes & banquettes-48
sectionals-14
chairs & chaises-81
ottomans & benches-76
cocktail tables-subid=42
side tables-subid=78
center tables & game tables-subid=942,79
desk & consoles-34,72
bookcases & display cabinets-subid=92,57
bar & bar carts-70
mirrors, trays & accents-subid=17,1507,130
lighting-132

Dining Room Ids
dining tables-74
center tables-subid=942
dining chairs-73
settes & banquettes-48
bar & counter stools-61
chests-32
consoles & credenzas-subid=61
bar & bar carts-70
bookcases & display cabinets-subid=92,57
mirrors, trays & accents-subid=17,1507,130

BedRoom Ids
beds-25
dressers-29
chests-32
nightstands & bedside tables-subid=82
chairs & chaises-81
mirrors, trays & accents-subid=17,1507,130
lighting-132

Outdoor - different than the rest - https://www.hickorychair.com/products/showresults?CollectionID=G3
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

# Category configurations with room type and IDs to scrape
# Format: {"name": "Category Name", "room_type": "Room Type", "ids": "TypeID or SubTypeID value", "is_subtype": True/False, "is_collection": True/False}
CATEGORIES = [
    # Living Room
    {"name": "Sofas & Loveseats", "room_type": "Living Room", "ids": "79", "is_subtype": False, "is_collection": False},
    {"name": "Settees & Banquettes", "room_type": "Living Room", "ids": "48", "is_subtype": False, "is_collection": False},
    {"name": "Sectionals", "room_type": "Living Room", "ids": "14", "is_subtype": False, "is_collection": False},
    {"name": "Chairs & Chaises", "room_type": "Living Room", "ids": "81", "is_subtype": False, "is_collection": False},
    {"name": "Ottomans & Benches", "room_type": "Living Room", "ids": "76", "is_subtype": False, "is_collection": False},
    {"name": "Cocktail Tables", "room_type": "Living Room", "ids": "42", "is_subtype": True, "is_collection": False},
    {"name": "Side Tables", "room_type": "Living Room", "ids": "78", "is_subtype": True, "is_collection": False},
    {"name": "Center Tables & Game Tables", "room_type": "Living Room", "ids": "942,79", "is_subtype": True, "is_collection": False},
    {"name": "Desks & Consoles", "room_type": "Living Room", "ids": "34,72", "is_subtype": False, "is_collection": False},
    {"name": "Bookcases & Display Cabinets", "room_type": "Living Room", "ids": "92,57", "is_subtype": True, "is_collection": False},
    {"name": "Bar & Bar Carts", "room_type": "Living Room", "ids": "70", "is_subtype": False, "is_collection": False},
    {"name": "Mirrors, Trays & Accents", "room_type": "Living Room", "ids": "17,1507,130", "is_subtype": True, "is_collection": False},
    {"name": "Lighting", "room_type": "Living Room", "ids": "132", "is_subtype": False, "is_collection": False},

    # Dining Room
    {"name": "Dining Tables", "room_type": "Dining Room", "ids": "74", "is_subtype": False, "is_collection": False},
    {"name": "Center Tables", "room_type": "Dining Room", "ids": "942", "is_subtype": True, "is_collection": False},
    {"name": "Dining Chairs", "room_type": "Dining Room", "ids": "73", "is_subtype": False, "is_collection": False},
    {"name": "Settees & Banquettes", "room_type": "Dining Room", "ids": "48", "is_subtype": False, "is_collection": False},
    {"name": "Bar & Counter Stools", "room_type": "Dining Room", "ids": "61", "is_subtype": False, "is_collection": False},
    {"name": "Chests", "room_type": "Dining Room", "ids": "32", "is_subtype": False, "is_collection": False},
    {"name": "Consoles & Credenzas", "room_type": "Dining Room", "ids": "61", "is_subtype": True, "is_collection": False},
    {"name": "Bar & Bar Carts", "room_type": "Dining Room", "ids": "70", "is_subtype": False, "is_collection": False},
    {"name": "Bookcases & Display Cabinets", "room_type": "Dining Room", "ids": "92,57", "is_subtype": True, "is_collection": False},
    {"name": "Mirrors, Trays & Accents", "room_type": "Dining Room", "ids": "17,1507,130", "is_subtype": True, "is_collection": False},

    # Bedroom
    {"name": "Beds", "room_type": "Bedroom", "ids": "25", "is_subtype": False, "is_collection": False},
    {"name": "Dressers", "room_type": "Bedroom", "ids": "29", "is_subtype": False, "is_collection": False},
    {"name": "Chests", "room_type": "Bedroom", "ids": "32", "is_subtype": False, "is_collection": False},
    {"name": "Nightstands & Bedside Tables", "room_type": "Bedroom", "ids": "82", "is_subtype": True, "is_collection": False},
    {"name": "Chairs & Chaises", "room_type": "Bedroom", "ids": "81", "is_subtype": False, "is_collection": False},
    {"name": "Mirrors, Trays & Accents", "room_type": "Bedroom", "ids": "17,1507,130", "is_subtype": True, "is_collection": False},
    {"name": "Lighting", "room_type": "Bedroom", "ids": "132", "is_subtype": False, "is_collection": False},

    # Outdoor (uses CollectionID instead of TypeID/SubTypeID)
    {"name": "Outdoor Furniture", "room_type": "Outdoor", "ids": "G3", "is_subtype": False, "is_collection": True},
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


def extract_products_from_listing_page(html: str, base_url: str, products_by_sku: Dict[str, Dict], category_url: str = None, category_name: str = None, room_type: str = None) -> List[Dict]:
    """
    Extract product data from a listing page HTML.

    Args:
        html: HTML content of listing page
        base_url: Base URL for resolving relative links
        products_by_sku: Dictionary mapping SKUs to product data (for deduplication and room merging)
        category_url: Category URL for room type extraction (optional)
        category_name: Category name for product type inference (optional)
        room_type: Explicit room type to add to this product (optional)

    Returns:
        List of product dictionaries (newly found in this page)
    """
    soup = BeautifulSoup(html, 'html.parser')
    new_products = []

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

            if not sku:
                continue

            # Check if we've already seen this SKU
            if sku in products_by_sku:
                # Product exists - merge room types
                existing_product = products_by_sku[sku]
                if room_type and room_type not in existing_product['room_types']:
                    existing_product['room_types'].append(room_type)
                    print(f"  [~] Updated {sku} - added room: {room_type}")
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

            # Categorize product with category name for better inference
            categorization = categorize_product(name, category_url, category_name)

            # Use explicit room_type if provided, otherwise use categorization
            room_types = [room_type] if room_type else categorization['room_types']

            product_data = {
                "name": name,
                "sku": sku,
                "img_url": img_url,
                "product_url": product_url,
                "price": None,  # No price available
                "in_stock": None,  # No stock status available
                "room_types": room_types,
                "product_type": categorization['product_type']
            }

            products_by_sku[sku] = product_data
            new_products.append(product_data)
            print(f"  [+] Found: {sku} - {name}")

        except Exception as e:
            print(f"  [-] Error extracting product from item: {e}")
            continue

    return new_products


def build_category_url(category: Dict) -> str:
    """
    Build URL based on category configuration.

    Args:
        category: Category dictionary with 'ids', 'is_subtype', and 'is_collection' keys

    Returns:
        Full URL for the category
    """
    ids = category['ids']
    is_subtype = category['is_subtype']
    is_collection = category.get('is_collection', False)

    if is_collection:
        return f"{BASE_URL}/Products/ShowResults?CollectionID={ids}"
    elif is_subtype:
        return f"{BASE_URL}/Products/ShowResults?SubTypeID={ids}"
    else:
        return f"{BASE_URL}/Products/ShowResults?TypeID={ids}"


def scrape_category(driver, category: Dict, products_by_sku: Dict[str, Dict]) -> int:
    """
    Scrape all products from a single category listing page.

    Args:
        driver: Selenium WebDriver instance
        category: Category dictionary with name, room_type, ids, and is_subtype
        products_by_sku: Dictionary mapping SKUs to product data (for deduplication and room merging)

    Returns:
        Number of new products found in this category
    """
    url = build_category_url(category)
    category_name = category['name']
    room_type = category['room_type']

    print(f"\nScraping {category_name} ({room_type}): {url}")

    html = fetch_page_with_selenium(driver, url, wait_for_selector=PRODUCT_ITEM_SELECTOR)

    if not html:
        print(f"  [-] Failed to fetch page for {category_name}")
        return 0

    # Pass category name and room type for better categorization
    new_products = extract_products_from_listing_page(html, BASE_URL, products_by_sku, url, category_name, room_type)

    print(f"  New products from {category_name}: {len(new_products)}")
    print(f"  Total unique products so far: {len(products_by_sku)}")

    return len(new_products)


def scrape(num_pages=None, max_products=None):
    """
    Main scraping function that matches the interface of other scrapers.

    Args:
        num_pages: Not used for Hickory Chair (scrapes all categories)
        max_products: Maximum number of products to scrape before stopping

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "hickorychair"

    print("=" * 80)
    print("Hickory Chair Product Scraper")
    print("=" * 80)
    print(f"Scraping {len(CATEGORIES)} categories")
    print("\nCategory URLs:")
    for i, category in enumerate(CATEGORIES, 1):
        url = build_category_url(category)
        print(f"  {i}. {category['name']} ({category['room_type']})")
        print(f"     {url}")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    products_by_sku = {}  # Track products by SKU, allowing room type merging

    # Create Selenium driver
    driver = create_driver()

    try:
        for category in CATEGORIES:
            new_count = scrape_category(driver, category, products_by_sku)

            # Check if we've hit max_products limit
            if max_products and len(products_by_sku) >= max_products:
                print(f"\n[!] Reached max_products limit ({max_products}), stopping")
                break

    finally:
        driver.quit()

    # Convert dictionary to list
    all_products = list(products_by_sku.values())

    # Trim to max_products if needed
    if max_products and len(all_products) > max_products:
        all_products = all_products[:max_products]

    print(f"\n{'=' * 80}")
    print(f"Total unique products scraped: {len(all_products)}")
    print(f"Total unique SKUs: {len(products_by_sku)}")
    print("=" * 80)

    # Save to JSON file (backup)
    print("\nSaving to JSON (backup)")
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    print(f"[+] Backup saved to: {output_path}")

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
