# Multi-Vendor Product Scraper

A Python-based web scraping system that extracts product data from multiple furniture manufacturer websites and syncs them to a Supabase database.

## Overview

This project scrapes product information (name, SKU, image URL, price, stock status) from various furniture vendor websites and stores the data in a centralized Supabase database. It handles pagination, async fetching, and automatic synchronization with database cleanup.

## Features

- **Multi-vendor support**: Currently supports HVL Group, Woodbridge Furniture, Bernhardt, Hickory Chair, and Sherrill Furniture
- **Rotating proxy support**: Built-in proxy rotation for resilience against rate limiting and IP bans
- **Async scraping**: Efficient parallel fetching of product detail pages
- **Database sync**: Automatic upsert and cleanup of stale products in Supabase
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
