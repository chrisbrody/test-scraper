import requests
from bs4 import BeautifulSoup
import json
import os

# Handle both direct execution and module import
try:
    from .supabase_utils import sync_products_to_supabase
    from .proxy_utils import get_proxy_manager, add_delay
except ImportError:
    from supabase_utils import sync_products_to_supabase
    from proxy_utils import get_proxy_manager, add_delay

def scrape(num_pages=1, max_products=None):
    """
    Scrapes product data from woodbridgefurniture.com and uploads to Supabase

    Args:
        num_pages: Number of pages to scrape (default: 2)
        max_products: Maximum number of products to scrape before stopping (default: None)

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "woodbridgefurniture"

    # Base URL pattern (will need to determine pagination format)
    base_url = "https://www.woodbridgefurniture.com/products?p={}"

    # Initialize products list
    all_products = []

    print(f"Starting scrape of {num_pages} page(s)...")

    # Loop through pages
    for page_num in range(1, num_pages + 1):
        url = base_url.format(page_num) if num_pages > 1 else "https://www.woodbridgefurniture.com/products"
        print(f"\nFetching page {page_num}: {url}")

        # Make HTTP GET request with proxy support
        try:
            proxy_manager = get_proxy_manager()
            response = proxy_manager.make_request_with_retry(url, method='GET', max_retries=3, timeout=30)

            if not response:
                print(f"Error fetching page {page_num}: All retries failed")
                continue

            # Add delay to mimic human behavior
            add_delay(1.0, 2.0)
        except Exception as e:
            print(f"Error fetching page {page_num}: {e}")
            continue

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all product links
        product_links = soup.find_all('a', class_='product-item-link')

        print(f"Found {len(product_links)} products on page {page_num}")

        # Extract data from each product
        for idx, product_link in enumerate(product_links, 1):
            try:
                # Extract Name
                name_elem = product_link.find('strong', class_='product-item-name')
                name = name_elem.get_text(strip=True) if name_elem else None

                # Extract SKU
                sku_elem = product_link.find('span', class_='product-item-sku')
                if sku_elem:
                    sku_text = sku_elem.get_text(strip=True)
                    # Extract just the SKU number (format: "SKU 1002-13 as shown")
                    sku = sku_text.replace("SKU", "").split("as shown")[0].strip() if "SKU" in sku_text else None
                else:
                    sku = None

                # Extract Image URL
                img_elem = product_link.find('img', class_='product-image-photo')
                img_url = img_elem.get('src') if img_elem else None

                # Extract Product URL
                product_url = product_link.get('href') if product_link.get('href') else None

                # Skip products without SKU
                if not sku:
                    print(f"  Skipping product {idx}: No SKU found")
                    continue

                # Create product dictionary (consistent field order across all scrapers)
                product_data = {
                    "name": name,
                    "sku": sku,
                    "img_url": img_url,
                    "product_url": product_url,
                    "price": None,  # Woodbridge doesn't show price on listing page
                    "in_stock": None  # Woodbridge doesn't show stock status on listing page
                }

                all_products.append(product_data)
                print(f"  Scraped product {idx}: {name} ({sku})")

                # Check if we've hit the max product limit
                if max_products and len(all_products) >= max_products:
                    print(f"\n⚠️  Reached max product limit ({max_products}). Stopping scrape.")
                    break

            except Exception as e:
                print(f"  Error extracting product {idx} on page {page_num}: {e}")
                continue

        # Break outer loop if max products reached
        if max_products and len(all_products) >= max_products:
            break

    # Upload to Supabase
    sync_stats = {}
    try:
        sync_stats = sync_products_to_supabase(all_products, vendor)
    except Exception as e:
        print(f"Error syncing to Supabase: {e}")

    # Also save to JSON file as backup
    output_file = os.path.join("data", f"{vendor}.json")
    try:
        os.makedirs("data", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=4, ensure_ascii=False)
        print(f"\nBackup saved to {output_file}")
    except Exception as e:
        print(f"Error saving to JSON: {e}")

    # Return statistics
    return {
        "vendor": vendor,
        "scraped_count": len(all_products),
        **sync_stats
    }

def main():
    """
    Main function for running scraper standalone
    """
    scrape(num_pages=2)

if __name__ == "__main__":
    main()
