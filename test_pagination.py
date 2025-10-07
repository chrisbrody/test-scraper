"""
Test pagination URL generation
"""
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

category_url = "https://www.bernhardt.com/products/luxury-bedroom-furniture"
PAGE_SIZE = 48

for page_num in range(1, 3):
    start = (page_num - 1) * PAGE_SIZE

    # Construct paginated URL
    parsed = urlparse(category_url)
    query_params = parse_qs(parsed.query)
    query_params['start'] = [str(start)]

    new_query = urlencode(query_params, doseq=True)
    paginated_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

    print(f"Page {page_num} (start={start}): {paginated_url}")
