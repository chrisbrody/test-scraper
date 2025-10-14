Goal: Create a Python script (scraper.py) that scrapes product data from a single, specified vendor website (Bernhardt.com). It will:
Discover individual product URLs from multiple provided category/listing pages (using traditional HTML parsing and pagination if present).
Visit each discovered product page to extract detailed information primarily from JSON-LD, precisely matching the provided Bernhardt structure.
The extracted fields are: Name, Img Url, Price, Sku, In Stock?, Room Types (array), and Product Type.
The output should be a JSON file named bernhardt.json.

IMPORTANT - Product Categorization:
All scrapers MUST include categorization for room types and product types:
- room_types: Array of room categories (e.g., ["Bedroom", "Living Room"])
- product_type: Single product category (e.g., "Bed", "Sofa", "Chair")

Use the categorization_utils.py helper to automatically categorize products:
1. Extract room type from category URL if available
2. Infer product type from product name using keyword matching
3. Fall back to multi-purpose categories if unable to determine

The categorization taxonomies are defined in:
- taxonomies/room_types.json
- taxonomies/product_types.json
Directory Structure:
A scrapers folder containing scraper.py.
A data folder (this exists) where bernhardt.json will be saved.
Libraries to Use: (if there are existing alternative already installed use those first)
requests (for initial synchronous page fetches, if aiohttp is not suitable for pagination).
BeautifulSoup4 for parsing HTML.
json for saving the output.
asyncio and aiohttp for efficient, asynchronous fetching of individual product detail pages.
re (regular expressions) for JSON-LD extraction if needed.
os for path manipulation.
Step 1: Define Target URLs & HTML Selectors for Product URL Discovery
Crucial Input for Claude:
BASE_URL: https://www.bernhardt.com
CATEGORY_URLS: An array of category/listing URLs (e.g., https://www.bernhardt.com/products/luxury-dining-room-furniture/).
PRODUCT_LINK_SELECTOR: 'a.ng-scope[href*="/shop/"]' (derived from your HTML example).
PAGINATION_NEXT_SELECTOR: 'a[aria-label="Next page"]' (common for Angular sites, but should be verified on Bernhardt.com).
Step 2: Define JSON-LD Extraction on Product Detail Pages (and Fallback)
Provided Bernhardt JSON-LD Example:
code
JSON
{
  "@context": "http://schema.org/",
  "@type": "Product",
  "name": "Odette Fabric Canopy Bed King",
  "image": "https://s3.amazonaws.com/emuncloud-staticassets/productImages/bh074/medium/K1325.jpg?1.0.81.20131-5af2ed11a2+bernhardt-20230616+bernhardt+umbraco+prod+cms=no-cache&m=undefined&=im2025-02-19T19:18:01.6530000Z",
  "sku": "K1325",
  "mpn": "662997121856",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "USD",
    "price": 13143,
    "itemCondition": "http://schema.org/New",
    "availability": "http://schema.org/InStock"
  }
}
Claude should now precisely define JSON_LD_MAPPING based on this example:
Name: data['name']
Img Url: data['image'] (it's a string, not a list, in this example)
Price: data['offers']['price']
Sku: data['sku']
In Stock?: Check if data['offers']['availability'] contains "InStock" (or is exactly "http://schema.org/InStock").
Fallback Selectors: The extract_data_from_html_fallback function should still be included as a safeguard, but with generic placeholder selectors, as the primary focus is on the reliable JSON-LD.
Step 3: Structure the Python Script (scraper.py)
The scraper.py file will be created inside a scrapers directory.
Imports: (As previously defined)

IMPORTANT: Import categorization utility at the top:
```python
try:
    from .categorization_utils import categorize_product
except ImportError:
    from categorization_utils import categorize_product
```

Global Configuration:
code
Python
# --- Configuration for User to Update ---
BASE_URL = "https://www.bernhardt.com"
CATEGORY_URLS = [
    f"{BASE_URL}/products/luxury-dining-room-furniture/", # Initial URL
    # Add more Bernhardt category URLs here as needed by the user
]
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT_FILE = 'bernhardt.json'

# Selectors for finding product links on category pages
PRODUCT_LINK_SELECTOR = 'a.ng-scope[href*="/shop/"]'
PAGINATION_NEXT_SELECTOR = 'a[aria-label="Next page"]' # Common for Angular sites, verify on Bernhardt

# --- JSON-LD Specific Key Mapping (PRECISION FOR BERNHARDT.COM) ---
JSON_LD_MAPPING = {
    "Name": ["name"],
    "Img Url": ["image"],
    "Price": ["offers", "price"],
    "Sku": ["sku"],
    "In Stock?": ["offers", "availability"] # Will be interpreted as boolean
}
# --- END JSON-LD Specific Key Mapping ---

# Fallback Selectors (placeholders, for product *detail* page HTML if JSON-LD fails)
FALLBACK_NAME_SELECTOR = 'h1.product-detail-name' # Generic
FALLBACK_IMG_URL_SELECTOR = 'img.product-detail-image' # Generic, get src attribute
FALLBACK_PRICE_SELECTOR = 'span.product-detail-price' # Generic
FALLBACK_SKU_SELECTOR = 'span.product-detail-sku' # Generic
FALLBACK_STOCK_STATUS_SELECTOR = 'span.product-detail-stock' # Generic
discover_product_urls(session, start_url) function:
Process: As previously defined, but ensuring the use of PRODUCT_LINK_SELECTOR for a.ng-scope[href*="/shop/"] and PAGINATION_NEXT_SELECTOR.
extract_data_from_json_ld(soup, product_url) function:
Process:
Finds <script type="application/ld+json"> tags.
Parses JSON.
Crucially, uses the refined JSON_LD_MAPPING to extract data.
For "Img Url": Directly uses data.get('image').
For "In Stock?": Interprets data.get('offers', {}).get('availability') to a boolean. Given the example uses "http://schema.org/InStock", the logic should check for that exact string.

IMPORTANT - Add Categorization:
After extracting basic product data, categorize the product:
```python
# Categorize product
categorization = categorize_product(product_name, category_url)

# Add to product dictionary
product_data["room_types"] = categorization['room_types']
product_data["product_type"] = categorization['product_type']
```

extract_data_from_html_fallback(soup) function:
Process: As previously defined (generic placeholders).
scrape_single_product_page(session, url) function:
Process: As previously defined, calling extract_data_from_json_ld first, then extract_data_from_html_fallback if necessary.
main() asynchronous function:
Process: As previously defined, iterating through CATEGORY_URLS for discovery and then asyncio.gather for detail extraction.
Execution Block: (As previously defined)

 make sure you this new scraper to the run_scraper.py like the other scrapers