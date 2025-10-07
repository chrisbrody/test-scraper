Goal: Create a Python script (scraper.py) that scrapes product data from a single, specified vendor website, extracting the following fields: Name, Img Url, Price, Sku, and In Stock?. The output should be a JSON file named products.json.
Libraries to Use:
requests for making HTTP requests.
BeautifulSoup4 for parsing HTML.
json for saving the output.
Steps for Claude:
Define the Target URL:
I will need a placeholder base_url and a product_list_url (or a single product_page_url if the data is on one page).
Crucial Input Required from User: The actual URL(s) to scrape. For now, I will use placeholders.
Identify HTML Selectors:
This is the most critical part. I will need to be told (or deduce from a provided URL/HTML snippet) the specific CSS selectors or XPath expressions for each piece of data.

example of product:
```
<div class="col-6 col-lg-4" id="grid-card-0">
    <div class="product-card quickview-card d-block position-relative" id="product-card-0">
        <div class="product-card-image position-relative border border-hvlg-beige">
            <a href="/Product/H1079101-AGB/" class="d-block " id="product-card-0-link">
                <img class="lozad w-100" data-src="https://cdnbf.hvlgroup.com:443/OXW4SQWH/as/4rqkp4p5wr3w29vxgzxk2ft/H1079101-AGB_001?auto=webp&amp;format=png&amp;width=500" id="product-card-0-image" src="https://cdnbf.hvlgroup.com:443/OXW4SQWH/as/4rqkp4p5wr3w29vxgzxk2ft/H1079101-AGB_001?auto=webp&amp;format=png&amp;width=500" data-loaded="true">
                    <div class="quickview-button mx-lg-2 ">
                        <button class="btn btn-hvlg-cream font-main right-arrow p-2 py-lg-3 px-lg-4 w-100 quickview-data" data-itemcode="H1079101-AGB" id="product-card-0-quick-view">Quick View</button>
                    </div>
            </a>
        </div>
        <div class="product-card-info brand3 py-3 px-2 mb-5">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div class="label-2" id="product-card-0-brand">
                    MITZI
                </div>
                
                <a href="/Account/Favorites/247867" class="btn btn-link p-0 favorites-heart" data-ajax="true" data-ajax-method="POST" data-ajax-complete="ManageFavoriteIcon" title="Add to Favorites">
                    <i data-favoritesid="247867" class="fal fa-heart"></i>                
                </a>            
            </div>
            <div class="mb-0">
                <h5 class="float-start text-capitalize mb-0" id="product-card-0-marketing-name">
                    acacia wall sconce
                </h5>
                <div class="label-1 fw-bold float-lg-end text-end">
                    <div id="product-card-0-price">$312</div>
                </div>
                <div class="clearfix"></div>
            </div>
            <div class="p2 mb-0 font-main" id="product-card-0-item-code">SKU: H1079101-AGB</div>
                <div class="p2 mb-0 font-main" id="product-card-0-stock-status">Estimated 12/14/2025</div>
            <div class="d-md-flex justify-content-between">
                <div class="mb-3 mb-md-0">
                    <div class="p2 mb-2" id="product-card-0-dimensions">
                        10.5" W x 10" H
                    </div>
                    
                </div>
            </div>
        </div>
    </div>
</div>
```

Structure the Python Script (scraper.py):
Imports: requests, BeautifulSoup, json.
main function: Orchestrates the scraping process.
Initializes an empty list all_products = [].
Makes HTTP GET request: Uses requests.get(url) to fetch the page content.
Error Handling: Checks response.status_code. If not 200, prints an error and exits.
Parses HTML: Uses BeautifulSoup(response.content, 'html.parser').
Finds Product Containers: Identifies the main HTML element that encapsulates a single product listing (e.g., a div with class product-card). Iterates through these.
Extracts Data per Product:
For each product container, it will try to find the Name, Img Url, Price, Sku, and In Stock? using the defined selectors.
Name: Extract text.
Img Url: Extract src attribute.
Price: Extract text. Clean up (remove currency symbols, convert to float if desired, though string is fine for JSON).
SKU: Extract text.
In Stock?: Extract text and interpret it (e.g., if text contains "In Stock", True, otherwise False).
Appends to list: Creates a dictionary for each product and appends it to all_products.
Saves to JSON: After iterating, uses json.dump(all_products, f, indent=4) to save the data to products.json.
Execution Block: if __name__ == "__main__": main()