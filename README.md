# Multi-Vendor Product Scraper

A Python-based web scraping system that extracts product data from multiple furniture manufacturer websites and syncs them to a Supabase database.

## Overview

This project scrapes product information (name, SKU, image URL, price, stock status) from various furniture vendor websites and stores the data in a centralized Supabase database. It handles pagination, async fetching, and automatic synchronization with database cleanup.

## Features

- **Multi-vendor support**: Currently supports HVL Group, Woodbridge Furniture, and Bernhardt
- **Async scraping**: Efficient parallel fetching of product detail pages
- **Database sync**: Automatic upsert and cleanup of stale products in Supabase
- **Batch processing**: Configurable batch sizes and product limits
- **JSON-LD extraction**: Structured data parsing from product schema markup
- **Fallback parsing**: HTML-based extraction when structured data is unavailable
- **Centralized runner**: Single script to execute all scrapers with custom configurations

## Project Structure

```
test-direct-mfg-scraper/
├── scrapers/
│   ├── __init__.py
│   ├── hvlgroup.py           # HVL Group scraper
│   ├── woodbridgefurniture.py # Woodbridge Furniture scraper
│   ├── bernhardt.py          # Bernhardt scraper
│   └── supabase_utils.py     # Database sync utilities
├── data/
│   ├── hvlgroup.json
│   ├── woodbridgefurniture.json
│   └── bernhardt_products.json
├── run_scrapers.py           # Main scraper runner
├── supabase_setup.sql        # Database schema
├── .env                      # Environment variables
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
pip install requests beautifulsoup4 aiohttp supabase python-dotenv
```

3. Set up environment variables in `.env`:
```env
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_service_role_key_here
```

4. Run the database setup script in your Supabase SQL editor:
```bash
# Execute supabase_setup.sql in Supabase dashboard
```

## Usage

### Running All Scrapers

Execute all enabled scrapers sequentially:

```bash
python run_scrapers.py
```

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
}

MAX_PRODUCTS_PER_BATCH = 500  # Limit products per vendor
```

### Running Individual Scrapers

Import and run a specific scraper:

```python
from scrapers import hvlgroup

stats = hvlgroup.scrape(num_pages=5, max_products=300)
print(stats)
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
- **Method**: Async product discovery + JSON-LD extraction
- **Output**: `data/bernhardt_products.json`
- **Features**:
  - Discovers product URLs from category pages
  - Extracts structured JSON-LD data
  - Falls back to HTML parsing if needed

## Data Schema

Each product record contains:

```json
{
  "name": "Product Name",
  "sku": "PROD123",
  "img_url": "https://example.com/image.jpg",
  "product_url": "https://example.com/product/prod123",
  "price": 1299.99,
  "in_stock": true,
  "vendor": "hvlgroup"
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

- **Upsert**: Products are inserted or updated based on (SKU, vendor) uniqueness
- **Cleanup**: Products removed from vendor websites are deleted from the database
- **Batch processing**: Products are synced in configurable batches (default: 100)

## Output

Sample scraping output:

```
============================================================
STARTING MULTI-VENDOR SCRAPER
============================================================

============================================================
SCRAPING: HVLGROUP
============================================================
Starting scrape of 3 pages...
Fetching page 1...
Found 60 products on page 1
...
Syncing 180 products to Supabase for vendor: hvlgroup...
✓ hvlgroup complete

============================================================
SCRAPING COMPLETE - SUMMARY
============================================================
Vendors scraped: 3
Total products scraped: 450
Total upserted: 445
Total errors: 5
Total deleted: 12
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
3. Use `supabase_utils.sync_products_to_supabase()` for database sync
4. Add configuration to `run_scrapers.py`

Example:

```python
# scrapers/newvendor.py
from .supabase_utils import sync_products_to_supabase

def scrape(num_pages=1, max_products=None):
    vendor = "newvendor"
    products = []

    # Your scraping logic here

    stats = sync_products_to_supabase(products, vendor)
    return {
        "scraped_count": len(products),
        **stats
    }
```

## Notes

- Respect robots.txt and rate limits
- Use appropriate User-Agent headers
- Some sites may require additional headers or cookies
- Angular/JS-heavy sites may need Selenium or Playwright

## License

Internal use only.
