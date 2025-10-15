import requests
from bs4 import BeautifulSoup
import json
import os

# Handle both direct execution and module import
try:
    from .supabase_utils import sync_products_to_supabase
    from .proxy_utils import get_proxy_manager, add_delay
    from .categorization_utils import categorize_product
except ImportError:
    from supabase_utils import sync_products_to_supabase
    from proxy_utils import get_proxy_manager, add_delay
    from categorization_utils import categorize_product

def scrape(num_pages=1, max_products=None):
    """
    Scrapes product data from hvlgroup.com and uploads to Supabase

    Args:
        num_pages: Number of pages to scrape (default: 1)
        max_products: Maximum number of products to scrape before stopping (default: None)

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "hvlgroup"

    # Base URL pattern
    base_url = "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=7240&CurrentPageId=1&pageNumber={}&tabId=a1c56b62-bc7f-4596-9373-73793cb563de"

    # Initialize products list
    all_products = []

    print(f"Starting scrape of {num_pages} pages...")

    # Loop through pages
    for page_num in range(1, num_pages + 1):
        url = base_url.format(page_num)
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

        # Find all product containers
        product_containers = soup.find_all('div', class_='product-card')

        print(f"Found {len(product_containers)} products on page {page_num}")

        # Extract data from each product
        for idx, product in enumerate(product_containers, 1):
            try:
                # Extract Name
                name_elem = product.find('h5', id=lambda x: x and 'marketing-name' in x)
                name = name_elem.get_text(strip=True) if name_elem else None

                # Extract SKU
                sku_elem = product.find('div', id=lambda x: x and 'item-code' in x)
                sku_text = sku_elem.get_text(strip=True) if sku_elem else None
                # Clean up SKU (remove "SKU: " prefix)
                sku = sku_text.replace("SKU:", "").strip() if sku_text else None

                # Extract Image URL
                img_elem = product.find('img', class_='lozad')
                img_url = img_elem.get('src') or img_elem.get('data-src') if img_elem else None

                # Extract Product URL
                link_elem = product.find('a', id=lambda x: x and 'link' in x)
                product_url = None
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    product_url = f"https://hvlgroup.com{href}" if not href.startswith('http') else href

                # Extract Price
                price_elem = product.find('div', id=lambda x: x and 'price' in x)
                price = None
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Remove dollar sign and convert to float
                    try:
                        price = float(price_text.replace('$', '').replace(',', '').strip())
                    except (ValueError, AttributeError):
                        price = None

                # Extract Stock Status (store as text)
                stock_elem = product.find('div', id=lambda x: x and 'stock-status' in x)
                in_stock = stock_elem.get_text(strip=True) if stock_elem else None

                # Skip products without SKU
                if not sku:
                    print(f"  Skipping product {idx}: No SKU found")
                    continue

                # Categorize product
                categorization = categorize_product(name, product_url)

                # Create product dictionary (consistent field order across all scrapers)
                product_data = {
                    "name": name,
                    "sku": sku,
                    "img_url": img_url,
                    "product_url": product_url,
                    "price": price,
                    "in_stock": in_stock,
                    "room_types": categorization['room_types'],
                    "product_type": categorization['product_type']
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
    scrape(num_pages=1)

if __name__ == "__main__":
    main()
