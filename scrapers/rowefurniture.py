"""
Rowe Furniture Product Scraper
Scrapes product data directly from listing pages using Selenium for AJAX rendering.
Does not visit individual product pages since price/availability data requires login.

Target URLs:
- https://rowefurniture.com/storage (Office storage - cabinets/consoles)
- https://rowefurniture.com/office-chairs (Office/Dining Room chairs)
"""

import json
import os
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Handle both direct execution and module import
try:
    from .categorization_utils import categorize_product
except ImportError:
    from categorization_utils import categorize_product

# --- Configuration ---
BASE_URL = "https://rowefurniture.com"

# Category configurations with URL and categorization rules
CATEGORIES = [
    {
        "name": "Office Storage",
        "url": f"{BASE_URL}/storage",
        "room_types": ["Office"],
        "product_type_keywords": {
            "cabinet": "Cabinet",
            "console": "Console",
            "credenza": "Console",
            "bookcase": "Bookcase",
            "shelf": "Bookcase",
        }
    },
    {
        "name": "Office Chairs",
        "url": f"{BASE_URL}/office-chairs",
        "room_types": ["Office", "Dining Room"],
        "product_type_override": "Chair",
    },
    {
        "name": "Office Desks",
        "url": f"{BASE_URL}/desks",
        "room_types": ["Office"],
        "product_type_override": "Desk",
    },
    {
        "name": "Dining Chairs & Banquettes",
        "url": f"{BASE_URL}/dining-chairs-banquettes",
        "room_types": ["Dining Room"],
        # No override - let categorization detect Chair vs Settee from product names
    },
]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT_FILE = 'rowefurniture_products.json'

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

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def scroll_to_load_all_products(driver, max_scrolls=10):
    """
    Scroll down the page to trigger lazy loading of all products

    Args:
        driver: Selenium WebDriver instance
        max_scrolls: Maximum number of scroll attempts
    """
    last_height = driver.execute_script("return document.body.scrollHeight")

    for i in range(max_scrolls):
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait for new content to load
        time.sleep(2)

        # Calculate new scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            # No new content loaded
            break

        last_height = new_height
        print(f"  Scrolled {i+1} times, page height: {new_height}")


def scrape_category(driver, category_config: Dict, max_products: Optional[int] = None) -> List[Dict]:
    """
    Scrape all products directly from a category listing page

    Args:
        driver: Selenium WebDriver instance
        category_config: Category configuration dictionary
        max_products: Maximum number of products to scrape from this category

    Returns:
        List of product data dictionaries
    """
    category_name = category_config['name']
    category_url = category_config['url']

    print(f"\n{'=' * 80}")
    print(f"Scraping Category: {category_name}")
    print(f"URL: {category_url}")
    print(f"{'=' * 80}")

    try:
        driver.get(category_url)

        # Wait for product items to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "product-item"))
            )
        except TimeoutException:
            print("  Warning: Timeout waiting for product items")
            return []

        # Scroll to load all products (lazy loading)
        scroll_to_load_all_products(driver)

        # Get page source after loading
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Find all product items using the correct class
        product_items = soup.find_all('div', class_='product-item')
        print(f"  Found {len(product_items)} product items")

        products = []

        for item in product_items:
            try:
                # Extract product name from h2.product-title
                title_elem = item.find('h2', class_='product-title')
                if not title_elem:
                    continue

                link = title_elem.find('a', href=True)
                if not link:
                    continue

                name = link.get_text(strip=True)
                href = link.get('href', '').strip()
                product_url = urljoin(BASE_URL, href)

                # Extract SKU from div.sku
                sku_elem = item.find('div', class_='sku')
                sku = sku_elem.get_text(strip=True) if sku_elem else href.split('/')[-1].upper()

                # Extract image from picture div
                picture_div = item.find('div', class_='picture')
                img_url = ''
                if picture_div:
                    img_elem = picture_div.find('img', class_='picture-img')
                    if img_elem:
                        img_url = img_elem.get('src', '')

                # Categorize product
                room_types = category_config.get('room_types', ['Multi-Purpose'])

                # Determine product type
                product_type = None
                name_lower = name.lower()

                # Check if category has a product_type_override
                if 'product_type_override' in category_config:
                    product_type = category_config['product_type_override']
                # Check if category has keyword mappings
                elif 'product_type_keywords' in category_config:
                    for keyword, ptype in category_config['product_type_keywords'].items():
                        if keyword in name_lower:
                            product_type = ptype
                            break

                # If still no product type, use categorization utility
                if not product_type:
                    categorization = categorize_product(name, category_url)
                    product_type = categorization['product_type']

                product_data = {
                    "name": name,
                    "sku": sku,
                    "img_url": img_url,
                    "product_url": product_url,
                    "price": None,  # Prices not displayed without login
                    "in_stock": None,  # Stock not shown on listing
                    "room_types": room_types,
                    "product_type": product_type
                }

                products.append(product_data)
                print(f"  [+] {sku} - {name}")

                # Check if we've hit the limit
                if max_products and len(products) >= max_products:
                    print(f"  Reached max_products limit ({max_products})")
                    break

            except Exception as e:
                print(f"  [-] Error extracting product: {e}")
                continue

        print(f"\n  Total products scraped from {category_name}: {len(products)}")
        return products

    except Exception as e:
        print(f"  Error scraping category: {e}")
        import traceback
        traceback.print_exc()
        return []


def scrape(num_pages=None, max_products=None):
    """
    Main scraping function that matches the interface of other scrapers.

    Args:
        num_pages: Not used for Rowe Furniture (scrapes all products from categories)
        max_products: Maximum number of products to scrape before stopping

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "rowefurniture"

    print("=" * 80)
    print("Rowe Furniture Product Scraper")
    print("=" * 80)
    print(f"Scraping {len(CATEGORIES)} categories")
    print("\nCategory URLs:")
    for i, category in enumerate(CATEGORIES, 1):
        print(f"  {i}. {category['name']}")
        print(f"     {category['url']}")
        print(f"     Room Types: {', '.join(category['room_types'])}")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_products = []

    # Create Selenium driver
    driver = create_driver()

    try:
        for category in CATEGORIES:
            # Calculate remaining products if max_products is set
            remaining = None
            if max_products:
                remaining = max_products - len(all_products)
                if remaining <= 0:
                    print(f"\n[!] Reached max_products limit ({max_products}), stopping")
                    break

            category_products = scrape_category(driver, category, remaining)
            all_products.extend(category_products)

    finally:
        driver.quit()

    print(f"\n{'=' * 80}")
    print(f"Total products scraped: {len(all_products)}")
    print(f"{'=' * 80}")

    # Save to JSON file (don't push to DB per user request)
    print("\nSaving to JSON")
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    print(f"[+] Saved to: {output_path}")

    # Return stats (no DB sync per user request)
    stats = {
        "scraped_count": len(all_products),
        "success_count": len(all_products),
        "error_count": 0,
        "deleted_count": 0
    }

    print("\n" + "=" * 80)
    print("Scraping Complete")
    print("=" * 80)

    return stats


if __name__ == "__main__":
    # When run directly, scrape all categories
    scrape()
