# Multi-Vendor Product Scraper

A Python-based web scraping system that extracts product data from multiple furniture manufacturer websites, categorizes them with room types and product types, and optionally syncs them to a Supabase database.

## Overview

This project scrapes product information (name, SKU, image URL, price, stock status, room types, product types) from various furniture vendor websites and stores the data first as JSON files for review, then optionally uploads to a centralized Supabase database. The workflow is separated into two stages: **scraping** (data collection) and **saving** (database upload), giving you full control over data review before uploading.

## Features

- **Multi-vendor support**: Currently supports HVL Group, Woodbridge Furniture, Bernhardt, Hickory Chair, Sherrill Furniture, and Rowe Furniture
- **Separated workflow**: Scrape → Review JSON → Upload to database (optional)
- **Product categorization**: Automatic categorization of products by room types and product types using taxonomy files
- **Rotating proxy support**: Built-in proxy rotation for resilience against rate limiting and IP bans
- **Flexible data saving**: Upload all vendors at once or select specific vendors
- **Database sync**: Smart upsert with change detection and cleanup of stale products
- **Batch processing**: Configurable batch sizes and product limits
- **JSON-LD extraction**: Structured data parsing from product schema markup
- **Fallback parsing**: HTML-based extraction when structured data is unavailable
- **Centralized runner**: Single script to execute all scrapers with custom configurations
- **Human-like behavior**: Random delays and request throttling to avoid detection

## Project Structure

```
test-direct-mfg-scraper/
├── scrapers/
│   ├── __init__.py
│   ├── hvlgroup.py              # HVL Group scraper
│   ├── woodbridgefurniture.py   # Woodbridge Furniture scraper
│   ├── bernhardt.py             # Bernhardt scraper (Selenium + API)
│   ├── hickorychair.py          # Hickory Chair scraper (Selenium)
│   ├── sherrillfurniture.py     # Sherrill Furniture scraper (Selenium)
│   ├── rowefurniture.py         # Rowe Furniture scraper (Selenium)
│   ├── categorization_utils.py  # Product categorization logic
│   ├── proxy_utils.py           # Rotating proxy manager
│   └── supabase_utils.py        # Database sync utilities
├── taxonomies/
│   ├── room_types.json          # Room type taxonomy
│   └── product_types.json       # Product type taxonomy
├── data/
│   ├── hvlgroup.json
│   ├── woodbridgefurniture.json
│   ├── bernhardt_products.json
│   ├── hickorychair_products.json
│   ├── sherrillfurniture_products.json
│   └── rowefurniture_products.json
├── run_scrapers.py              # Main scraper runner (scraping only)
├── save_data.py                 # Database uploader (Supabase sync)
├── supabase_setup.sql           # Database schema
├── .env.example                 # Environment variables template
└── README.md
```

## Setup

### Prerequisites

- Python 3.8+
- Supabase account and project

### Installation

1. Clone the repository:
```bash
cd test-direct-mfg-scraper
```

2. Install required dependencies:
```bash
pip install requests beautifulsoup4 aiohttp supabase python-dotenv selenium
```

3. Set up environment variables in `.env`:
```env
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_service_role_key_here

# Proxy Configuration (Optional but Recommended)
PROXY_ENABLED=true
PROXY_TYPE=residential  # residential or datacenter
PROXY_LIST=ip1:port1,ip2:port2,ip3:port3
PROXY_USERNAME=your_username  # Optional, if proxies require auth
PROXY_PASSWORD=your_password  # Optional, if proxies require auth
PROXY_ROTATION_DELAY=1.5  # Delay between requests in seconds
```

See `.env.example` for a complete template.

4. Run the database setup script in your Supabase SQL editor:
```bash
# Execute supabase_setup.sql in Supabase dashboard
```

## Usage

### Quick Start

```bash
# 1. Scrape all vendors (saves to JSON files)
python run_scrapers.py

# 2. Review the JSON files in data/ folder
ls data/

# 3. Upload to Supabase
python save_data.py                    # All vendors
python save_data.py hvlgroup bernhardt # Specific vendors only
```

### Workflow Overview

The scraping process is separated into two stages:

1. **Scrape**: Collect data from websites and save to JSON files
2. **Save**: Upload JSON data to Supabase database (optional)

This separation allows you to:
- Review scraped data before uploading
- Manually edit JSON files if needed
- Selectively upload specific vendors
- Re-upload without re-scraping

### Stage 1: Scraping Data

Execute all enabled scrapers to collect data:

```bash
python run_scrapers.py
```

This will:
- Scrape all enabled vendors
- Save data to `data/` folder as JSON files
- Display scraping statistics
- **NOT** upload to database (gives you time to review)

### Stage 2: Uploading to Database

After reviewing the JSON files, upload to Supabase:

```bash
# Upload all vendors
python save_data.py

# Upload specific vendors only
python save_data.py hvlgroup bernhardt
python save_data.py hickorychair
```

This will:
- Read JSON files from `data/` folder
- Upload to Supabase with smart change detection
- Skip unchanged products
- Delete discontinued products
- Display detailed statistics

### Configuration

Edit `run_scrapers.py` to configure individual scrapers:

```python
SCRAPERS = {
    "hvlgroup": {
        "enabled": True,        # Enable/disable scraper
        "scraper": hvlgroup.scrape,
        "pages": 3,             # Number of pages to scrape
        "async": False,
    },
    "woodbridgefurniture": {
        "enabled": True,
        "scraper": woodbridgefurniture.scrape,
        "pages": 2,
        "async": False,
    },
    "bernhardt": {
        "enabled": True,
        "scraper": bernhardt.scrape,
    },
    "hickorychair": {
        "enabled": True,
        "scraper": hickorychair.scrape,
    },
    "sherrillfurniture": {
        "enabled": True,
        "scraper": sherrillfurniture.scrape,
    },
}

MAX_PRODUCTS_PER_BATCH = 500  # Limit products per vendor
```

### Running Individual Scrapers

Run a specific scraper directly:

```bash
# Navigate to scrapers directory
cd scrapers

# Run individual scraper
python hvlgroup.py
python bernhardt.py
python hickorychair.py
```

Or import and run programmatically:

```python
from scrapers import hvlgroup

# Scrape and save to JSON only
stats = hvlgroup.scrape(num_pages=5, max_products=300)
print(stats)  # {'vendor': 'hvlgroup', 'scraped_count': 300}
```

## Scrapers

### HVL Group (`hvlgroup.py`)
- **URL**: https://hvlgroup.com
- **Method**: Pagination-based scraping of product listing pages
- **Output**: `data/hvlgroup.json`

### Woodbridge Furniture (`woodbridgefurniture.py`)
- **URL**: https://woodbridgefurniture.com
- **Method**: Similar pagination approach
- **Output**: `data/woodbridgefurniture.json`

### Bernhardt (`bernhardt.py`)
- **URL**: https://www.bernhardt.com
- **Method**: API-based scraping with Selenium fallback + JSON-LD extraction
- **Output**: `data/bernhardt_products.json`
- **Features**:
  - Uses Bernhardt API endpoint for faster scraping
  - Selenium-based product detail extraction
  - Extracts structured JSON-LD data
  - Falls back to HTML parsing if needed

### Hickory Chair (`hickorychair.py`)
- **URL**: https://www.hickorychair.com
- **Method**: Selenium-based scraping with infinite scroll
- **Output**: `data/hickorychair_products.json`
- **Features**:
  - Handles JavaScript-rendered content
  - Automatic scroll to load all products
  - JSON-LD extraction from product pages

### Sherrill Furniture (`sherrillfurniture.py`)
- **URL**: https://www.sherrillfurniture.com
- **Method**: Selenium-based scraping with infinite scroll
- **Output**: `data/sherrillfurniture_products.json`
- **Features**:
  - JavaScript-rendered product listings
  - Automatic scroll pagination
  - JSON-LD structured data extraction

## Product Categorization

All products are automatically categorized with room types and product types using taxonomy files.

### Taxonomies

The project includes two taxonomy files that define the categorization structure:

#### `taxonomies/room_types.json`

Defines all possible room categories for products:

```json
{
  "room_types": [
    "Living Room",
    "Dining Room",
    "Bedroom",
    "Office",
    "Bathroom",
    "Kitchen",
    "Outdoor",
    "Hallway",
    "Entrance",
    "Multi-Purpose"
  ]
}
```

#### `taxonomies/product_types.json`

Defines product categories with keywords for automatic matching:

```json
{
  "product_types": {
    "Sofa": {
      "keywords": ["sofa", "couch", "sectional", "loveseat"]
    },
    "Chair": {
      "keywords": ["chair", "armchair", "accent chair", "side chair"]
    },
    "Table": {
      "keywords": ["table", "desk", "console"]
    },
    "Bed": {
      "keywords": ["bed", "headboard", "footboard"]
    },
    "Lighting": {
      "keywords": ["lamp", "chandelier", "sconce", "pendant", "light", "fixture"]
    }
    // ... more categories
  }
}
```

### Categorization Logic

The `categorization_utils.py` module automatically categorizes products:

1. **Room Type Detection**:
   - Extracts room type from category URL (e.g., "/bedroom/" → "Bedroom")
   - Checks product name for room keywords
   - Falls back to "Multi-Purpose" if unable to determine

2. **Product Type Detection**:
   - Matches product name against keyword lists in taxonomy
   - Uses category name for additional context
   - Falls back to "Other" if no match found

3. **Special Handling**:
   - **Lighting products**: Enhanced categorization with fixture types (Chandelier, Wall Sconce, Pendant, etc.)
   - **Multi-room products**: Can belong to multiple rooms (e.g., "Dining Chair" → ["Dining Room", "Office"])

### Example Categorization

```python
from scrapers.categorization_utils import categorize_product

# Categorize a product
result = categorize_product(
    product_name="Modern Leather Sectional Sofa",
    category_url="https://example.com/living-room/sofas"
)

print(result)
# {
#   'room_types': ['Living Room'],
#   'product_type': 'Sofa'
# }
```

### Customizing Taxonomies

To add or modify categories:

1. Edit `taxonomies/room_types.json` to add new room types
2. Edit `taxonomies/product_types.json` to add new product categories or keywords
3. Restart scrapers to use updated taxonomies

## Data Schema

Each product record contains:

```json
{
  "name": "Product Name",
  "sku": "PROD123",
  "img_url": "https://example.com/image.jpg",
  "product_url": "https://example.com/product/prod123",
  "price": 1299.99,
  "in_stock": "In stock",
  "room_types": ["Living Room", "Bedroom"],
  "product_type": "Chair",
  "fixture_type": "Chandelier"  // Only for lighting products
}
```

**Database Schema** (with vendor added during upload):

```json
{
  "id": "uuid",
  "name": "Product Name",
  "sku": "PROD123",
  "vendor": "hvlgroup",
  "img_url": "https://example.com/image.jpg",
  "product_url": "https://example.com/product/prod123",
  "price": 1299.99,
  "in_stock": "In stock",
  "room_types": ["Living Room", "Bedroom"],
  "product_type": "Chair",
  "fixture_type": "Chandelier",  // Optional, only for lighting
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

## Database

### Supabase Schema

```sql
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    sku TEXT NOT NULL,
    vendor TEXT NOT NULL,
    img_url TEXT,
    product_url TEXT,
    price NUMERIC(10,2),
    in_stock BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(sku, vendor)
);
```

### Sync Behavior

The `save_data.py` script provides intelligent database synchronization:

- **Smart upsert**: Products are inserted or updated based on (SKU, vendor) uniqueness
- **Change detection**: Only updates products when data has actually changed (skips unchanged products)
- **Cleanup**: Products removed from vendor websites are automatically deleted from the database
- **Batch processing**: Products are synced in configurable batches (default: 100)
- **Statistics**: Detailed reporting of added, updated, skipped, and deleted products

Example sync output:
```
==================================================
Syncing 180 products to Supabase for vendor: hvlgroup...
Batch size: 100
Skip unchanged: True
==================================================

Fetching existing products from database...
Found 150 existing products in database

Processing batch 1/2 (100 products)...
+ Added: PROD001 (ABC123)
↻ Updated: PROD002 (DEF456)
⊘ Skipped (unchanged): PROD003 (GHI789)
...

==================================================
Removing hvlgroup products no longer on website...
==================================================
✓ Deleted: OLD123
✓ Deleted: OLD456
Deleted 2 discontinued products

==================================================
Sync complete!
Added/Updated: 30
Skipped (unchanged): 148
Errors: 0
Deleted: 2
==================================================
```

## Output

### Scraping Output (`run_scrapers.py`)

```
============================================================
STARTING MULTI-VENDOR SCRAPER
============================================================

============================================================
SCRAPING: HVLGROUP
============================================================
Starting scrape of 9 room categories...

============================================================
Scraping: Bedroom (CurrentPageId=31)
Pages to scrape: 54
============================================================

Fetching page 1: https://hvlgroup.com/Products/Paging?...
Found 60 products on page 1
  [+] New: SKU123 - Modern Table Lamp
      Fixture: Table Lamp, Rooms: Bedroom
...

[SUCCESS] Total unique products: 3238

=== Fixture Type Summary ===
  Chandelier: 1250
  Wall Sconce: 890
  Pendant: 650
  ...

[SUCCESS] Saved to data/hvlgroup.json

============================================================
Scraping Complete
============================================================

✓ hvlgroup complete - 3238 products saved to JSON

============================================================
SCRAPING COMPLETE - SUMMARY
============================================================
Vendors scraped: 6
Total products scraped: 8450

JSON files saved to: data/
To upload to Supabase, run: python save_data.py
============================================================
```

### Upload Output (`save_data.py`)

```
============================================================
SAVING ALL VENDORS TO SUPABASE
============================================================
Vendors: hvlgroup, woodbridgefurniture, bernhardt, hickorychair, sherrillfurniture, rowefurniture

============================================================
LOADING: HVLGROUP
============================================================
File: data/hvlgroup.json
  ✓ Loaded 3238 products from JSON

==================================================
Syncing 3238 products to Supabase for vendor: hvlgroup...
==================================================
+ Added: PROD001
↻ Updated: PROD002
⊘ Skipped (unchanged): PROD003
...

✓ hvlgroup complete

============================================================
SYNC COMPLETE - SUMMARY
============================================================
Vendors synced: 6
Total products loaded: 8450
Total upserted: 125
Total skipped (unchanged): 8250
Total errors: 0
Total deleted: 75
============================================================
```

## Error Handling

- HTTP errors are caught and logged per page/product
- Missing data fields use `None` or empty strings as defaults
- Failed scrapers don't prevent others from running
- Database errors are logged with detailed messages

## Development

### Adding a New Scraper

1. Create a new file in `scrapers/` (e.g., `newvendor.py`)
2. Implement the `scrape(num_pages, max_products)` function
3. Import and use `categorize_product()` for product categorization
4. Save to JSON only (no direct database upload)
5. Add configuration to `run_scrapers.py` and `save_data.py`

Example:

```python
# scrapers/newvendor.py
import json
import os

try:
    from .categorization_utils import categorize_product
except ImportError:
    from categorization_utils import categorize_product

def scrape(num_pages=1, max_products=None):
    vendor = "newvendor"
    products = []

    # Your scraping logic here
    for product in scraped_products:
        # Categorize each product
        categorization = categorize_product(
            product['name'],
            category_url
        )

        product_data = {
            "name": product['name'],
            "sku": product['sku'],
            "img_url": product['img_url'],
            "product_url": product['product_url'],
            "price": product['price'],
            "in_stock": product['in_stock'],
            "room_types": categorization['room_types'],
            "product_type": categorization['product_type']
        }
        products.append(product_data)

    # Save to JSON
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f'{vendor}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Saved to {output_path}")

    # Return stats
    return {
        "vendor": vendor,
        "scraped_count": len(products)
    }
```

Then add to `run_scrapers.py`:
```python
from scrapers import newvendor

SCRAPERS = {
    # ... existing scrapers
    "newvendor": {
        "enabled": True,
        "scraper": newvendor.scrape,
    },
}
```

And add to `save_data.py`:
```python
VENDOR_FILES = {
    # ... existing vendors
    "newvendor": "newvendor.json",
}
```

## Proxy Configuration

### Why Use Proxies?

When scraping multiple vendor websites, using rotating proxies is **highly recommended** to:
- Avoid IP bans and rate limiting
- Distribute requests across multiple IPs
- Maintain access to target websites over time
- Mimic organic traffic patterns

### Proxy Types

1. **Residential Proxies** (Recommended)
   - Best for high-resistance websites
   - Less likely to be blocked
   - Higher cost but more reliable
   - Use for: Bernhardt, Hickory Chair, Sherrill Furniture (Selenium-based scrapers)

2. **Datacenter Proxies**
   - Good for less restrictive websites
   - Lower cost, higher speed
   - May be blocked on some sites
   - Use for: HVL Group, Woodbridge Furniture (simple HTTP scrapers)

### Setting Up Proxies

#### Option 1: Proxy List Format

Add your proxies to `.env` in one of these formats:

```env
# Simple format (IP:PORT)
PROXY_LIST=192.168.1.1:8080,192.168.1.2:8080,192.168.1.3:8080

# With authentication embedded
PROXY_LIST=http://user:pass@192.168.1.1:8080,http://user:pass@192.168.1.2:8080

# Using separate auth credentials (applies to all proxies)
PROXY_LIST=192.168.1.1:8080,192.168.1.2:8080
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password
```

#### Option 2: Proxy Service Providers

Popular proxy services:
- **Bright Data** (formerly Luminati): Premium residential/datacenter proxies
- **Smartproxy**: Affordable residential proxies
- **Oxylabs**: Enterprise-grade proxies
- **ScraperAPI**: Managed proxy rotation with API

Example for ScraperAPI:
```env
PROXY_ENABLED=true
PROXY_LIST=proxy-server.scraperapi.com:8001
PROXY_USERNAME=scraperapi
PROXY_PASSWORD=your_api_key
```

### How Proxy Rotation Works

The `proxy_utils.py` module provides:

1. **Automatic Rotation**: Proxies rotate after each request
2. **Retry Logic**: Failed requests automatically retry with a different proxy
3. **Delay Management**: Configurable delays between requests to mimic human behavior
4. **Dual Support**: Works with both `requests` library and Selenium WebDriver

### Proxy Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `PROXY_ENABLED` | `false` | Enable/disable proxy rotation |
| `PROXY_TYPE` | `residential` | Type of proxy (for documentation) |
| `PROXY_LIST` | `` | Comma-separated list of proxies |
| `PROXY_USERNAME` | `` | Authentication username (optional) |
| `PROXY_PASSWORD` | `` | Authentication password (optional) |
| `PROXY_ROTATION_DELAY` | `0.5` | Delay between requests (seconds) |

### Error Handling

The proxy manager automatically:
- Rotates to the next proxy on connection errors
- Retries failed requests up to 3 times
- Logs proxy failures for debugging
- Falls back to direct connection if all proxies fail (when `PROXY_ENABLED=false`)

### Best Practices

1. **Combine Proxies with Delays**: Use `PROXY_ROTATION_DELAY` to add random delays (1-3 seconds) between requests
2. **Monitor Proxy Health**: Check logs for repeated proxy failures
3. **Use Quality Proxies**: Avoid free proxies - they're unreliable and often already blocked
4. **Rotate Frequently**: For high-volume scraping, rotate after every request
5. **Match Proxy Type to Target**: Use residential proxies for JavaScript-heavy sites (Selenium scrapers)

### Example: Complete Proxy Setup

```env
# .env file
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# Enable proxies with residential IPs
PROXY_ENABLED=true
PROXY_TYPE=residential
PROXY_LIST=proxy1.example.com:8080,proxy2.example.com:8080,proxy3.example.com:8080
PROXY_USERNAME=your_proxy_user
PROXY_PASSWORD=your_proxy_pass
PROXY_ROTATION_DELAY=2.0  # 2 second delay to mimic human behavior
```

### Testing Proxies

Test your proxy configuration:

```python
from scrapers.proxy_utils import get_proxy_manager

# Get proxy manager
pm = get_proxy_manager()

# Make a test request
response = pm.make_request_with_retry('https://httpbin.org/ip')
if response:
    print(f"Request successful from IP: {response.json()}")
else:
    print("All proxies failed")

# Check stats
print(pm.get_stats())
```

## Notes

- Respect robots.txt and rate limits
- **Always use proxies** for production scraping to avoid IP bans
- Combine proxies with delays (`time.sleep()`) to mimic human behavior
- Monitor proxy performance and replace failing proxies
- Some sites may require additional headers or cookies
- Angular/JS-heavy sites use Selenium with proxy support built-in

## License

Internal use only.
