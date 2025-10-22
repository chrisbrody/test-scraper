"""
Woodbridge Furniture Scraper with Room-Based Configuration
Scrapes by room type with configurable page counts for comprehensive coverage

Room URLs:
- Bar: https://www.woodbridgefurniture.com/products?room_type=5516 (3 total pages)
- Bedroom: https://www.woodbridgefurniture.com/products?room_type=5509 (4 total pages)
- Dining Room: https://www.woodbridgefurniture.com/products?room_type=5510
- Living Room: https://www.woodbridgefurniture.com/products?room_type=5511
- Office: https://www.woodbridgefurniture.com/products?room_type=5512
- Outdoor: https://www.woodbridgefurniture.com/products?room_type=5513
- Entrance: https://www.woodbridgefurniture.com/products?room_type=5514
- Bathroom: https://www.woodbridgefurniture.com/products?room_type=5515
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re

# Handle both direct execution and module import
try:
    from .proxy_utils import get_proxy_manager, add_delay
    from .categorization_utils import categorize_product
except ImportError:
    from proxy_utils import get_proxy_manager, add_delay
    from categorization_utils import categorize_product

def get_room_name_from_room_type(room_type_id):
    """
    Map room_type parameter to room name
    Based on Woodbridge Furniture's URL structure
    """
    room_map = {
        "5516": "Bar",
        "5509": "Bedroom",
        "5515": "Dining Room",
        "5513": "Hallway/Foyer",
        "5514": "Kitchen",
        "5510": "Library/Office",
        "5511": "Living Room",
        "5520": "Outdoor/Pool",
        # Add more mappings as discovered
    }
    return room_map.get(str(room_type_id), "Unknown")

def scrape(room_configs=None, max_products=None):
    """
    Scrapes product data from woodbridgefurniture.com using room configurations and uploads to Supabase

    Args:
        room_configs: List of dicts with 'url' and 'num_pages' keys
                      Example: [
                          {"url": "https://www.woodbridgefurniture.com/products?room_type=5516", "num_pages": 3},
                          {"url": "https://www.woodbridgefurniture.com/products?room_type=5509", "num_pages": 4}
                      ]
                      If None, uses default configuration (1 page per room for testing)
        max_products: Maximum number of products to scrape before stopping (default: None)

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "woodbridgefurniture"

    # Default configuration: 1 page per room for testing
    # Update num_pages values when ready for full scrape
    if room_configs is None:
        room_configs = [
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5516",
                "num_pages": 3  # Bar - 3 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5509",
                "num_pages": 4  # Bedroom - 4 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5515",
                "num_pages": 4  # Dining Room - 4 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5513",
                "num_pages": 3  # Hallway/Foyer - 3 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5514",
                "num_pages": 4  # Kitchen - 4 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5510",
                "num_pages": 1  # Library/Office - 5 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5511",
                "num_pages": 8  # Living Room - 8 total pages available
            },
            {
                "url": "https://www.woodbridgefurniture.com/products?room_type=5520",
                "num_pages": 2  # Outdoor/Pool - 2 total pages available
            }
        ]

    # Track products by SKU for deduplication
    products_by_sku = {}

    print(f"Starting scrape of {len(room_configs)} room categories...\n")

    for config in room_configs:
        base_url = config['url']
        num_pages = config['num_pages']

        # Extract room_type from URL to determine room
        room_type_match = re.search(r'room_type=(\d+)', base_url)
        room_from_url = None
        if room_type_match:
            room_type_id = room_type_match.group(1)
            room_from_url = get_room_name_from_room_type(room_type_id)
            print(f"\n{'='*60}")
            print(f"Scraping: {room_from_url} (room_type={room_type_id})")
            print(f"Pages to scrape: {num_pages}")
            print(f"{'='*60}")

        for page_num in range(1, num_pages + 1):
            # Build URL with page number
            # If URL already has ?p= parameter, replace it, otherwise add it
            if '?p=' in base_url or '&p=' in base_url:
                url = re.sub(r'[?&]p=\d+', f'&p={page_num}', base_url)
            else:
                separator = '&' if '?' in base_url else '?'
                url = f"{base_url}{separator}p={page_num}"

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

                    # Skip products without SKU
                    if not sku:
                        continue

                    # Check if product already exists (deduplication)
                    if sku in products_by_sku:
                        existing_product = products_by_sku[sku]
                        # Merge room types if this is a new room
                        if room_from_url and room_from_url not in existing_product['room_types']:
                            existing_product['room_types'].append(room_from_url)
                            print(f"  [~] Updated {sku} - added room: {room_from_url}")
                        continue

                    # Extract Image URL
                    img_elem = product_link.find('img', class_='product-image-photo')
                    img_url = img_elem.get('src') if img_elem else None

                    # Extract Product URL
                    product_url = product_link.get('href') if product_link.get('href') else None

                    # Categorize product - use room from URL and product name
                    categorization = categorize_product(name, product_url)

                    # Override room_types with the room from URL since we're scraping by room
                    room_types = [room_from_url] if room_from_url else categorization['room_types']

                    # Create product dictionary (consistent field order across all scrapers)
                    product_data = {
                        "name": name,
                        "sku": sku,
                        "img_url": img_url,
                        "product_url": product_url,
                        "price": None,  # Woodbridge doesn't show price on listing page
                        "in_stock": None,  # Woodbridge doesn't show stock status on listing page
                        "room_types": room_types,
                        "product_type": categorization['product_type'],
                        "fixture_type": categorization['fixture_type']
                    }

                    products_by_sku[sku] = product_data
                    print(f"  [+] New: {sku} - {name}")
                    print(f"      Product Type: {categorization['product_type']}, Rooms: {', '.join(room_types)}")

                    # Check if we've hit the max product limit
                    if max_products and len(products_by_sku) >= max_products:
                        print(f"\nReached max product limit ({max_products}). Stopping scrape.")
                        break

                except Exception as e:
                    print(f"  [-] Error extracting product: {e}")
                    continue

            # Break if max products reached
            if max_products and len(products_by_sku) >= max_products:
                break

        # Break outer loop if max products reached
        if max_products and len(products_by_sku) >= max_products:
            break

        print(f"\nTotal unique products so far: {len(products_by_sku)}")

    # Convert to list
    all_products = list(products_by_sku.values())

    # Print summary statistics
    print(f"\n{'='*60}")
    print(f"[SUCCESS] Total unique products: {len(all_products)}")

    product_type_counts = {}
    room_type_counts = {}
    multi_room_count = 0

    for product in all_products:
        prod_type = product.get('product_type', 'Unknown')
        product_type_counts[prod_type] = product_type_counts.get(prod_type, 0) + 1

        rooms = product.get('room_types', [])
        if len(rooms) > 1:
            multi_room_count += 1
        for room in rooms:
            room_type_counts[room] = room_type_counts.get(room, 0) + 1

    print("\n=== Product Type Summary ===")
    for prod_type, count in sorted(product_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {prod_type}: {count}")

    print("\n=== Room Type Summary ===")
    for room, count in sorted(room_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {room}: {count}")

    print(f"\n=== Multi-Room Products ===")
    print(f"  Products in multiple rooms: {multi_room_count}")

    # Save to JSON file
    output_file = os.path.join("data", f"{vendor}.json")
    try:
        os.makedirs("data", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=4, ensure_ascii=False)
        print(f"\n[SUCCESS] Saved to {output_file}")
    except Exception as e:
        print(f"Error saving to JSON: {e}")

    # Return statistics
    return {
        "vendor": vendor,
        "scraped_count": len(all_products),
    }

def main():
    """
    Main function for running scraper standalone
    Uses default configuration defined in scrape() function
    """
    scrape()

if __name__ == "__main__":
    main()
