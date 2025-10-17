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

def categorize_lighting_product(product_name, room_from_url=None):
    """
    Enhanced categorization specifically for lighting products

    Returns:
        dict with keys:
            - room_types: list of applicable rooms
            - product_type: main category (e.g., "Lighting")
            - fixture_type: sub-category (e.g., "Chandelier", "Wall Sconce")
    """
    name_lower = product_name.lower() if product_name else ""

    # Fixture type detection (sub-categories within lighting)
    fixture_types = {
        "Chandelier": ["chandelier"],
        "Wall Sconce": ["wall sconce", "sconce"],
        "Pendant": ["pendant"],
        "Flush Mount": ["flush mount", "ceiling mount"],
        "Semi-Flush Mount": ["semi-flush", "semi flush"],
        "Linear": ["linear"],
        "Recessed": ["recessed"],
        "Decorative Downlight": ["downlight", "down light"],
        "Table Lamp": ["table lamp"],
        "Floor Lamp": ["floor lamp"],
        "Desk Lamp": ["desk lamp"],
        "Vanity Light": ["vanity", "bath light"],
        "Picture Light": ["picture light"],
        "Outdoor": ["outdoor", "exterior"],
    }

    fixture_type = "Other Lighting"
    for fixture, keywords in fixture_types.items():
        if any(keyword in name_lower for keyword in keywords):
            fixture_type = fixture
            break

    # Room type detection (can be multiple)
    room_keywords = {
        "Bedroom": ["bedroom"],
        "Bathroom": ["bathroom", "bath", "vanity"],
        "Kitchen": ["kitchen"],
        "Dining Room": ["dining"],
        "Living Room": ["living room", "living"],
        "Office": ["office", "desk"],
        "Hallway": ["hallway", "entry", "foyer"],
        "Outdoor": ["outdoor", "exterior", "patio"],
    }

    detected_rooms = []

    # Add room from URL if provided
    if room_from_url:
        detected_rooms.append(room_from_url)

    # Check product name for additional room hints
    for room, keywords in room_keywords.items():
        if any(keyword in name_lower for keyword in keywords):
            if room not in detected_rooms:
                detected_rooms.append(room)

    # If no rooms detected, mark as multi-purpose
    if not detected_rooms:
        detected_rooms = ["Multi-Purpose"]

    return {
        "room_types": detected_rooms,
        "product_type": "Lighting",  # All products are lighting
        "fixture_type": fixture_type
    }

def get_room_name_from_page_id(page_id):
    """
    Map CurrentPageId to room name
    Based on HVL Group's URL structure
    """
    room_map = {
        "31": "Bedroom",
        "32": "Bathroom",
        "33": "Dining Room",
        "34": "Entrance",
        "35": "Hallway",
        "36": "Kitchen",
        "37": "Living Room",
        "1791": "Office",
        "5007": "Exterior",
    }
    return room_map.get(str(page_id), "Unknown")

def scrape(room_configs=None, max_products=None):
    """
    Scrapes product data from hvlgroup.com using room configurations and uploads to Supabase

    Args:
        room_configs: List of dicts with 'url' and 'num_pages' keys
                      Example: [
                          {"url": "https://...", "num_pages": 2},
                          {"url": "https://...", "num_pages": 5}
                      ]
                      If None, uses default configuration
        max_products: Maximum number of products to scrape before stopping (default: None)

    Returns:
        Dictionary with scraping statistics
    """
    vendor = "hvlgroup"

    # Default room configurations (all rooms, all pages)
    if room_configs is None:
        room_configs = [
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=3238&CurrentPageId=31&pageNumber=1",
                "num_pages": 54  #pages:54 Bedroom
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=1201&CurrentPageId=32&pageNumber=1",
                "num_pages": 21  #pages:21 Bathroom
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=4117&CurrentPageId=33&pageNumber=1",
                "num_pages": 69  #pages:69 Dining Room
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=3516&CurrentPageId=34&pageNumber=1",
                "num_pages": 59  #pages:59 Entrance
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=2469&CurrentPageId=35&pageNumber=1",
                "num_pages": 42  #pages:42 Hallway
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=1775&CurrentPageId=36&pageNumber=1",
                "num_pages": 30  #pages:30 Kitchen
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=3332&CurrentPageId=37&pageNumber=1",
                "num_pages": 56  #pages:56 Living Room
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=767&CurrentPageId=5007&pageNumber=1",
                "num_pages": 13  #pages:13 Exterior
            },
            {
                "url": "https://hvlgroup.com/Products/Paging?PageSize=60&TotalObjectCount=1413&CurrentPageId=1791&pageNumber=1",
                "num_pages": 24  #pages:24 Office
            }
        ]

    # Track products by SKU for deduplication
    products_by_sku = {}

    print(f"Starting scrape of {len(room_configs)} room categories...\n")

    for config in room_configs:
        base_url = config['url']
        num_pages = config['num_pages']

        # Extract CurrentPageId from URL to determine room
        page_id_match = re.search(r'CurrentPageId=(\d+)', base_url)
        room_from_url = None
        if page_id_match:
            page_id = page_id_match.group(1)
            room_from_url = get_room_name_from_page_id(page_id)
            print(f"\n{'='*60}")
            print(f"Scraping: {room_from_url} (CurrentPageId={page_id})")
            print(f"Pages to scrape: {num_pages}")
            print(f"{'='*60}")

        for page_num in range(1, num_pages + 1):
            # Replace pageNumber in URL
            url = re.sub(r'pageNumber=\d+', f'pageNumber={page_num}', base_url)
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
                    sku = sku_text.replace("SKU:", "").strip() if sku_text else None

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
                        try:
                            price = float(price_text.replace('$', '').replace(',', '').strip())
                        except (ValueError, AttributeError):
                            price = None

                    # Extract Stock Status
                    stock_elem = product.find('div', id=lambda x: x and 'stock-status' in x)
                    in_stock = stock_elem.get_text(strip=True) if stock_elem else None

                    # Enhanced categorization for lighting
                    categorization = categorize_lighting_product(name, room_from_url)

                    # Create product dictionary with enhanced lighting fields
                    product_data = {
                        "name": name,
                        "sku": sku,
                        "img_url": img_url,
                        "product_url": product_url,
                        "price": price,
                        "in_stock": in_stock,
                        "room_types": categorization['room_types'],
                        "product_type": categorization['product_type'],
                        "fixture_type": categorization['fixture_type']  # NEW: Sub-category
                    }

                    products_by_sku[sku] = product_data
                    print(f"  [+] New: {sku} - {name}")
                    print(f"      Fixture: {categorization['fixture_type']}, Rooms: {', '.join(categorization['room_types'])}")

                    # Check if we've hit the max product limit
                    if max_products and len(products_by_sku) >= max_products:
                        print(f"\n⚠️  Reached max product limit ({max_products}). Stopping scrape.")
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

    fixture_type_counts = {}
    room_type_counts = {}
    multi_room_count = 0

    for product in all_products:
        fixture = product.get('fixture_type', 'Unknown')
        fixture_type_counts[fixture] = fixture_type_counts.get(fixture, 0) + 1

        rooms = product.get('room_types', [])
        if len(rooms) > 1:
            multi_room_count += 1
        for room in rooms:
            room_type_counts[room] = room_type_counts.get(room, 0) + 1

    print("\n=== Fixture Type Summary ===")
    for fixture, count in sorted(fixture_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {fixture}: {count}")

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
    Uses default room_configs defined in scrape() function
    """
    scrape()

if __name__ == "__main__":
    main()
