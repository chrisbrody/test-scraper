"""
Bernhardt.com Product Scraper
HYBRID APPROACH (NEW - using API endpoint):
1. Fetches all product data from API endpoint
2. Matches SKUs with product URLs and images from category pages

OLD APPROACH (preserved below, commented out):
- Scrapes product data from Bernhardt category pages using Selenium for JS rendering and JSON-LD extraction
"""

import json
import os
import re
import time
import requests
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
    from .proxy_utils import get_proxy_manager, add_delay
except ImportError:
    from supabase_utils import sync_products_to_supabase
    from proxy_utils import get_proxy_manager, add_delay

# --- Configuration for User to Update ---
BASE_URL = "https://www.bernhardt.com"

# ===== NEW API-BASED CONFIGURATION =====
# API endpoints by category - each returns all products for that category
API_ENDPOINTS = [
    {
        "name": "Bedroom",
        "url": "https://www.bernhardt.com/service/QueryBernhardtProducts.json",
        "params": {
            "op": "ProductQuery1.4",
            "IncludeTagShards": "MultiViewPriceRange",
            "JsConfig": "ExcludeDefaultValues",
            "IncludeTagKinds": "Express Ship,InStock,NewIntroductions,BedSizes",
            "Fields": "Id,ShortDescription,Price,WholesalePrice,Category,ManufacturerNumber,OptionGroup,MinimumOrderQty,PurchaseIncrement,AvailableQty,ProductTags,isNew,IntroducedOn",
            "$clear": "true",
            "context": "shop",
            "fields": "Id,ShortDescription,Price,WholesalePrice,Category,ManufacturerNumber,OptionGroup,MinimumOrderQty,PurchaseIncrement,AvailableQty,ProductTags,isNew,IntroducedOn",
            "include": "Total",
            "orderBy": "BedroomPosition",
            "retailerId": "*",
            "skip": "0",
            "tagCriteria": '{"RoomType":["Bedroom"],"$MultiView":["Yes"]}',
            "take": "390"
        },
        "category_url": "https://www.bernhardt.com/products/luxury-bedroom-furniture",
        "pages": 9
    },
    # Add more categories as needed:
    # {
    #     "name": "Dining",
    #     "url": "https://www.bernhardt.com/service/QueryBernhardtProducts.json",
    #     "params": {...},
    #     "category_url": "https://www.bernhardt.com/products/luxury-dining-room-furniture",
    #     "pages": 7
    # },
]

# Selectors for finding product info on category pages (for SKU matching)
PRODUCT_LINK_SELECTOR = 'a[href^="/shop/"]'
PRODUCT_SKU_SELECTOR = 'span.product-id.ng-binding'

# ===== OLD SELENIUM-BASED CONFIGURATION (COMMENTED OUT, PRESERVED) =====
# # Category configuration with page ranges
# # Format: {"url": "category_url", "pages": number_of_pages}
# # Each page represents PAGE_SIZE (48) products, starting from page 1
# CATEGORIES = [
#     {
#         "url": "https://www.bernhardt.com/products/luxury-bedroom-furniture",
#         "pages": 9
#     },
#     # {
#     #     "url": "https://www.bernhardt.com/products/luxury-dining-room-furniture",
#     #     "pages": 7
#     # },
#     # {
#     #     "url": "https://www.bernhardt.com/products/luxury-living-room-furniture",
#     #     "pages": 23
#     # },
#     # {
#     #     "url": "https://www.bernhardt.com/products/luxury-home-office-room-furniture",
#     #     "pages": 2
#     # },
#     # {
#     #     "url": "https://www.bernhardt.com/products/luxury-outdoor-furniture",
#     #     "pages": 11
#     # }
# ]
#
# PAGE_SIZE = 48
#
# # --- JSON-LD Specific Key Mapping (PRECISION FOR BERNHARDT.COM) ---
# JSON_LD_MAPPING = {
#     "Name": ["name"],
#     "Img Url": ["image"],
#     "Price": ["offers", "price"],
#     "Sku": ["sku"],
#     "In Stock?": ["offers", "availability"]
# }
#
# # Fallback Selectors (placeholders, for product *detail* page HTML if JSON-LD fails)
# FALLBACK_NAME_SELECTOR = 'h1.product-detail-name'
# FALLBACK_IMG_URL_SELECTOR = 'img.product-detail-image'
# FALLBACK_PRICE_SELECTOR = 'span.product-detail-price'
# FALLBACK_SKU_SELECTOR = 'span.product-detail-sku'
# FALLBACK_STOCK_STATUS_SELECTOR = 'span.product-detail-stock'

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT_FILE = 'bernhardt_products.json'

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
                    # Extract price (convert to float/None)
                    price = None
                    try:
                        price_value = data.get('offers', {}).get('price')
                        if price_value not in [None, '']:
                            price = float(price_value)
                    except (ValueError, TypeError):
                        price = None

                    # Extract availability (store as text)
                    in_stock = None
                    availability = data.get('offers', {}).get('availability', '')
                    if availability:
                        # Extract readable status from schema.org URLs
                        if 'InStock' in availability:
                            in_stock = 'In stock'
                        elif 'OutOfStock' in availability:
                            in_stock = 'Out of stock'
                        else:
                            # Store the raw availability text if it's not a schema.org URL
                            in_stock = availability

                    # Create product dictionary (consistent field order across all scrapers)
                    product_data = {
                        "name": data.get('name', ''),
                        "sku": data.get('sku', ''),
                        "img_url": data.get('image', ''),
                        "product_url": product_url,
                        "price": price,
                        "in_stock": in_stock
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
    # Create product dictionary (consistent field order across all scrapers)
    product_data = {
        "name": "",
        "sku": "",
        "img_url": "",
        "product_url": product_url,
        "price": None,
        "in_stock": None
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


# ===== NEW API-BASED FUNCTIONS =====

def fetch_products_from_api(api_endpoint: Dict) -> List[Dict]:
    """
    Fetch all products from the Bernhardt API endpoint with proxy support.

    Args:
        api_endpoint: Dictionary containing API URL and params

    Returns:
        List of product dictionaries from API
    """
    try:
        print(f"\nFetching products from API: {api_endpoint['name']}")

        # Use proxy manager for request with automatic retry
        proxy_manager = get_proxy_manager()
        response = proxy_manager.make_request_with_retry(
            api_endpoint['url'],
            method='GET',
            params=api_endpoint['params'],
            timeout=30,
            max_retries=3
        )

        if not response:
            print(f"  [ERROR] Failed to fetch from API after retries")
            return []

        data = response.json()
        products = data.get('results', [])
        total = data.get('total', 0)

        print(f"  [OK] Fetched {len(products)} products from API (Total available: {total})")

        # Add delay to mimic human behavior
        add_delay(0.5, 1.5)

        return products

    except Exception as e:
        print(f"  [ERROR] Error fetching from API: {e}")
        return []


def extract_sku_url_image_map(html: str, base_url: str) -> Dict[str, Dict]:
    """
    Extract SKU -> {product_url, img_url} mapping from category page HTML.

    Args:
        html: HTML content of category page
        base_url: Base URL for resolving relative links

    Returns:
        Dictionary mapping SKU to product_url and img_url
    """
    soup = BeautifulSoup(html, 'html.parser')
    sku_map = {}

    # Find all product items (grid-item divs contain both SKU and link)
    grid_items = soup.select('div.grid-item')

    for item in grid_items:
        try:
            # Find SKU
            sku_elem = item.select_one(PRODUCT_SKU_SELECTOR)
            if not sku_elem:
                continue
            sku = sku_elem.get_text(strip=True)

            # Find product link
            link_elem = item.select_one(PRODUCT_LINK_SELECTOR)
            if not link_elem:
                continue
            href = link_elem.get('href')
            if href:
                clean_href = href.split('?')[0]
                product_url = urljoin(base_url, clean_href)
            else:
                continue

            # Find image URL
            img_elem = item.select_one('img')
            img_url = ''
            if img_elem:
                # Try different image attributes
                img_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src') or ''
                if img_url and not img_url.startswith('http'):
                    img_url = urljoin(base_url, img_url)

            sku_map[sku] = {
                'product_url': product_url,
                'img_url': img_url
            }

        except Exception as e:
            print(f"  Warning: Error extracting SKU mapping: {e}")
            continue

    return sku_map


def scrape_category_pages_for_skus(driver, category_url: str, max_pages: int) -> Dict[str, Dict]:
    """
    Scrape category pages to build SKU -> URL/Image mapping.

    Args:
        driver: Selenium WebDriver instance
        category_url: Starting category URL
        max_pages: Number of pages to scrape

    Returns:
        Dictionary mapping SKU to product_url and img_url
    """
    all_sku_map = {}

    print(f"\n  Scraping category pages for SKU mapping: {category_url}")
    print(f"  Pages to scrape: {max_pages}")

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
        print(f"    Page {page_num}/{max_pages}...", end=" ")

        # Wait for page to render
        time.sleep(3)

        # Get HTML and extract SKU mappings
        html = driver.page_source
        page_sku_map = extract_sku_url_image_map(html, BASE_URL)

        new_skus = len(page_sku_map) - len(set(page_sku_map.keys()) & set(all_sku_map.keys()))
        all_sku_map.update(page_sku_map)

        print(f"Found {len(page_sku_map)} SKUs ({new_skus} new, {len(all_sku_map)} total)")

        # Navigate to next page if not last
        if page_num < max_pages:
            try:
                # Get room type from URL
                room_type = "Bedroom"
                if "dining" in category_url.lower():
                    room_type = "Dining"
                elif "living" in category_url.lower():
                    room_type = "Living"
                elif "office" in category_url.lower():
                    room_type = "Office"
                elif "outdoor" in category_url.lower():
                    room_type = "Outdoor"

                next_page = page_num + 1
                next_url = f"{category_url}#?RoomType={room_type}&$MultiView=Yes&orderBy={room_type}Position&context=shop&page={next_page}"
                driver.execute_script(f"window.location.href = '{next_url}';")
                time.sleep(5)

                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.grid-item'))
                )
            except Exception as e:
                print(f"  [WARNING] Error navigating to next page: {e}")
                break

    print(f"  [OK] Total SKUs mapped: {len(all_sku_map)}")
    return all_sku_map


def merge_api_data_with_sku_map(api_products: List[Dict], sku_map: Dict[str, Dict]) -> List[Dict]:
    """
    Merge API product data with SKU mapping to create complete product records.

    Args:
        api_products: List of products from API
        sku_map: Dictionary mapping SKU to product_url and img_url

    Returns:
        List of complete product dictionaries
    """
    products = []
    matched_count = 0

    for api_product in api_products:
        sku = api_product.get('id', '')  # API uses 'id' field for SKU
        if not sku:
            continue

        # Get price
        price = None
        try:
            price_value = api_product.get('price')  # API uses lowercase 'price'
            if price_value not in [None, '']:
                price = float(price_value)
        except (ValueError, TypeError):
            price = None

        # Determine stock status
        in_stock = None
        available_qty = api_product.get('availableQty')  # API uses lowercase 'availableQty'
        if available_qty is not None:
            in_stock = 'In stock' if available_qty > 0 else 'Out of stock'

        # Check for InStock tag in 'tags' object
        tags = api_product.get('tags', {})
        if isinstance(tags, dict) and 'InStock' in tags:
            in_stock = 'In stock'

        # Get product URL and image URL from SKU map
        sku_data = sku_map.get(sku, {})
        product_url = sku_data.get('product_url', '')
        img_url = sku_data.get('img_url', '')

        if product_url and img_url:
            matched_count += 1

        # Create product dictionary
        product = {
            "name": api_product.get('shortDescription', ''),  # API uses lowercase 'shortDescription'
            "sku": sku,
            "img_url": img_url,
            "product_url": product_url,
            "price": price,
            "in_stock": in_stock
        }

        products.append(product)

    print(f"\n  Merged {len(products)} products from API")
    print(f"  Matched {matched_count} products with URLs and images from category pages")
    print(f"  {len(products) - matched_count} products missing URL/image data")

    return products


# ===== END NEW API-BASED FUNCTIONS =====


# ===== OLD SELENIUM-BASED FUNCTIONS (COMMENTED OUT, PRESERVED) =====
# All functions below are preserved but commented out. They can be re-enabled if needed.
#
# def discover_product_urls(html: str, base_url: str) -> Set[str]:
#     """Extract product URLs from a category page."""
#     ...
#
# def discover_all_product_urls_selenium(driver, category_url: str, max_pages: int) -> Set[str]:
#     """Discover all product URLs from a category by paginating through pages."""
#     ...
#
# def extract_data_from_json_ld(soup: BeautifulSoup, product_url: str) -> Optional[Dict]:
#     """Extract product data from JSON-LD structured data."""
#     ...
#
# def extract_data_from_html_fallback(soup: BeautifulSoup, product_url: str) -> Dict:
#     """Fallback method to extract product data from HTML if JSON-LD fails."""
#     ...
#
# def scrape_single_product_page_selenium(driver, url: str) -> Optional[Dict]:
#     """Scrape a single product page using Selenium."""
#     ...


def scrape(num_pages=None, max_products=None):
    """
    Main scraping function - NEW API-BASED APPROACH

    Hybrid approach that:
    1. Fetches all product data from API endpoint
    2. Scrapes category pages to get product URLs and images
    3. Merges data by matching SKUs

    Args:
        num_pages: Not used for Bernhardt (uses API_ENDPOINTS config instead)
        max_products: Maximum number of products to scrape before stopping

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "bernhardt"

    print("=" * 80)
    print("Bernhardt.com Product Scraper (NEW API-BASED)")
    print("=" * 80)

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_products = []

    # Step 1: Fetch product data from API endpoints
    print("\n" + "=" * 80)
    print("STEP 1: Fetching Product Data from API")
    print("=" * 80)

    all_api_products = []
    for api_endpoint in API_ENDPOINTS:
        api_products = fetch_products_from_api(api_endpoint)

        if not api_products:
            print(f"  [WARNING] No products fetched from {api_endpoint['name']} API")
            continue

        # Step 2: Scrape category pages to get SKU -> URL/Image mapping
        print(f"\nSTEP 2: Scraping category pages for {api_endpoint['name']} SKU mapping")
        print("=" * 80)

        driver = create_driver()
        try:
            sku_map = scrape_category_pages_for_skus(
                driver,
                api_endpoint['category_url'],
                api_endpoint['pages']
            )
        finally:
            driver.quit()

        # Step 3: Merge API data with SKU map
        print(f"\nSTEP 3: Merging {api_endpoint['name']} data")
        print("=" * 80)

        merged_products = merge_api_data_with_sku_map(api_products, sku_map)
        all_products.extend(merged_products)

        # Check if we've hit max_products limit
        if max_products and len(all_products) >= max_products:
            print(f"\n[WARNING] Reached max_products limit ({max_products}), stopping")
            all_products = all_products[:max_products]
            break

    print(f"\n{'=' * 80}")
    print(f"Total products processed: {len(all_products)}")
    print("=" * 80)

    # Step 4: Save to JSON file (backup)
    print("\n" + "=" * 80)
    print("STEP 4: Saving to JSON (backup)")
    print("=" * 80)

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    print(f"[OK] Backup saved to: {output_path}")

    # Step 5: Sync to Supabase (filter to only DB fields)
    print("\n" + "=" * 80)
    print("STEP 5: Syncing to Supabase")
    print("=" * 80)

    # Filter products to only include fields that exist in DB schema
    db_products = []
    for product in all_products:
        db_product = {
            "name": product.get("name"),
            "sku": product.get("sku"),
            "img_url": product.get("img_url"),
            "product_url": product.get("product_url"),
            "price": product.get("price"),
            "in_stock": product.get("in_stock"),
        }
        db_products.append(db_product)

    stats = sync_products_to_supabase(db_products, vendor)

    # Add scraped count to stats
    stats["scraped_count"] = len(all_products)

    print("\n" + "=" * 80)
    print("Scraping Complete")
    print("=" * 80)

    return stats


# ===== OLD SCRAPE FUNCTION (COMMENTED OUT, PRESERVED) =====
# def scrape_old_method(num_pages=None, max_products=None):
#     """
#     OLD: Main scraping function using Selenium to visit each product page.
#     This method is preserved but commented out.
#     """
#     vendor = "bernhardt"
#
#     print("=" * 80)
#     print("Bernhardt.com Product Scraper (OLD METHOD)")
#     print("=" * 80)
#
#     # Ensure output directory exists
#     os.makedirs(OUTPUT_DIR, exist_ok=True)
#
#     all_product_urls = set()
#
#     # Step 1: Use Selenium to discover product URLs from category pages
#     print("\n" + "=" * 80)
#     print("STEP 1: Discovering Product URLs (using Selenium)")
#     print("=" * 80)
#
#     driver = create_driver()
#
#     try:
#         for category in CATEGORIES:
#             category_url = category["url"]
#             max_pages = category["pages"]
#             category_products = discover_all_product_urls_selenium(driver, category_url, max_pages)
#             all_product_urls.update(category_products)
#
#             # Check if we've hit max_products limit
#             if max_products and len(all_product_urls) >= max_products:
#                 print(f"\n⚠ Reached max_products limit ({max_products}), stopping discovery")
#                 break
#     finally:
#         driver.quit()
#
#     print(f"\n{'=' * 80}")
#     print(f"Total unique products discovered: {len(all_product_urls)}")
#     print("=" * 80)
#
#     # Step 2: Scrape all product detail pages using Selenium
#     print("\n" + "=" * 80)
#     print("STEP 2: Scraping Product Details (using Selenium)")
#     print("=" * 80)
#
#     products = []
#     driver = create_driver()
#
#     try:
#         # Convert set to list and limit by max_products if specified
#         urls_to_scrape = list(all_product_urls)
#         if max_products:
#             urls_to_scrape = urls_to_scrape[:max_products]
#
#         for idx, url in enumerate(urls_to_scrape, 1):
#             print(f"[{idx}/{len(urls_to_scrape)}] Scraping: {url}")
#             product_data = scrape_single_product_page_selenium(driver, url)
#             if product_data:
#                 products.append(product_data)
#
#             # Small delay to be respectful
#             time.sleep(0.5)
#     finally:
#         driver.quit()
#
#     # Step 3: Save to JSON file (backup)
#     print("\n" + "=" * 80)
#     print("STEP 3: Saving to JSON (backup)")
#     print("=" * 80)
#
#     output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
#
#     with open(output_path, 'w', encoding='utf-8') as f:
#         json.dump(products, f, indent=2, ensure_ascii=False)
#
#     print(f"✓ Backup saved to: {output_path}")
#
#     # Step 4: Sync to Supabase (filter to only DB fields)
#     print("\n" + "=" * 80)
#     print("STEP 4: Syncing to Supabase")
#     print("=" * 80)
#
#     # Filter products to only include fields that exist in DB schema
#     db_products = []
#     for product in products:
#         db_product = {
#             "name": product.get("name"),
#             "sku": product.get("sku"),
#             "img_url": product.get("img_url"),
#             "product_url": product.get("product_url"),
#             "price": product.get("price"),
#             "in_stock": product.get("in_stock"),
#         }
#         db_products.append(db_product)
#
#     stats = sync_products_to_supabase(db_products, vendor)
#
#     # Add scraped count to stats
#     stats["scraped_count"] = len(products)
#
#     print("\n" + "=" * 80)
#     print("Scraping Complete")
#     print("=" * 80)
#
#     return stats


if __name__ == "__main__":
    # When run directly, scrape all pages
    scrape()
