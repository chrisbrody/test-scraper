"""
Product Categorization Utilities
Helper functions to categorize products into room types and product types
"""

import json
import os
import re
from typing import List, Optional

# Load taxonomies
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_DIR = os.path.join(SCRIPT_DIR, '..', 'taxonomies')

def load_taxonomy(filename: str) -> dict:
    """Load a taxonomy JSON file"""
    path = os.path.join(TAXONOMY_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Load taxonomies at module level
ROOM_TYPES = load_taxonomy('room_types.json')['room_types']
PRODUCT_TYPES = load_taxonomy('product_types.json')['product_types']


def extract_room_type_from_url(url: str) -> Optional[str]:
    """
    Extract room type from a category URL.

    Args:
        url: Category URL (e.g., "https://www.bernhardt.com/products/luxury-bedroom-furniture/")

    Returns:
        Room type name (e.g., "Bedroom") or None if not found
    """
    if not url:
        return None

    url_lower = url.lower()

    # Try to match against room type keywords
    for room_type in ROOM_TYPES:
        for keyword in room_type['keywords']:
            if keyword.lower() in url_lower:
                return room_type['name']

    return None


def infer_product_type_from_name(product_name: str) -> Optional[str]:
    """
    Infer product type from product name using keyword matching.

    Args:
        product_name: Product name (e.g., "Odette Fabric Canopy Bed King")

    Returns:
        Product type name (e.g., "Bed") or None if not found
    """
    if not product_name:
        return None

    name_lower = product_name.lower()

    # Build a list of (product_type_name, keyword, keyword_length) tuples
    # Sort by keyword length (descending) to match longer, more specific phrases first
    keyword_matches = []
    for product_type in PRODUCT_TYPES:
        for keyword in product_type['keywords']:
            keyword_matches.append((product_type['name'], keyword, len(keyword)))

    # Sort by keyword length in descending order (longest first)
    keyword_matches.sort(key=lambda x: x[2], reverse=True)

    # Try to match against product type keywords
    for product_type_name, keyword, _ in keyword_matches:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, name_lower):
            return product_type_name

    return None


def infer_room_types_from_product_type(product_type: str) -> List[str]:
    """
    Infer likely room types based on product type.

    Args:
        product_type: Product type (e.g., "Bed")

    Returns:
        List of likely room type names
    """
    # Mapping of product types to typical room types
    product_to_rooms = {
        "Bed": ["Bedroom"],
        "Nightstand": ["Bedroom"],
        "Dresser": ["Bedroom"],
        "Sofa": ["Living Room"],
        "Loveseat": ["Living Room"],
        "Chair": ["Living Room", "Dining Room", "Office", "Multi-Purpose"],
        "Chandelier": ["Dining Room", "Living Room", "Entryway", "Multi-Purpose"],
        "Pendant": ["Kitchen", "Dining Room", "Living Room", "Multi-Purpose"],
        "Wall Sconce": ["Entryway", "Bathroom", "Living Room", "Multi-Purpose"],
        "Table Lamp": ["Living Room", "Bedroom", "Office", "Multi-Purpose"],
        "Desk": ["Office"],
        "Bookcase": ["Office", "Living Room"],
        "Side Table": ["Living Room", "Bedroom", "Multi-Purpose"],
        "Drink Table": ["Living Room", "Multi-Purpose"],
        "Plant Stand": ["Living Room", "Entryway", "Multi-Purpose"],
        "Pillow": ["Living Room", "Bedroom", "Outdoor", "Multi-Purpose"],
    }

    return product_to_rooms.get(product_type, ["Multi-Purpose"])


def infer_product_type_from_category_name(category_name: str) -> Optional[str]:
    """
    Infer product type from a category name (e.g., from TypeID or SubTypeID metadata).

    Args:
        category_name: Category name (e.g., "sofas_loveseats", "dining_tables", "cocktail_tables")

    Returns:
        Product type name (e.g., "Sofa", "Table") or None if not found
    """
    if not category_name:
        return None

    category_lower = category_name.lower()

    # Mapping of category keywords to product types
    # Ordered by specificity (most specific first to avoid false matches)
    category_to_product_type = [
        # Most specific matches first
        ("nightstand", "Nightstand"),
        ("bedside", "Nightstand"),
        ("dining table", "Table"),  # Hickory Chair format (space-separated)
        ("dining_table", "Table"),
        ("cocktail table", "Table"),  # Hickory Chair format
        ("cocktail_table", "Table"),
        ("side table", "Side Table"),  # Hickory Chair format
        ("side_table", "Side Table"),
        ("center table", "Table"),  # Hickory Chair format
        ("center_table", "Table"),
        ("game table", "Table"),  # Hickory Chair format
        ("game_table", "Table"),
        ("sofa & loveseat", "Sofa"),  # Hickory Chair format
        ("sofas_loveseat", "Sofa"),  # Handle compound categories
        ("loveseat", "Loveseat"),
        ("sectional", "Sofa"),
        ("settee", "Settee"),
        ("banquette", "Settee"),
        ("chair & chaise", "Chair"),  # Hickory Chair format
        ("chairs_chaise", "Chair"),  # Plural form for category
        ("chaise", "Ottoman"),
        ("ottoman", "Ottoman"),
        ("bench", "Bench"),
        ("desk & console", "Desk"),  # Hickory Chair format (prioritize desk)
        ("desk", "Desk"),
        ("console & credenza", "Console"),  # Hickory Chair format
        ("console", "Console"),
        ("credenza", "Console"),
        ("dresser", "Dresser"),
        ("counter stool", "Stool"),  # Must be before "bar" to match "Bar & Counter Stools"
        ("bar stool", "Stool"),  # Must be before "bar" to match "Bar Stool" correctly
        ("bar & counter stool", "Stool"),  # Hickory Chair format - explicit match
        ("bar cart", "Bar Cart"),  # Hickory Chair format
        ("bar_cart", "Bar Cart"),
        ("bar & bar cart", "Bar Cart"),  # Hickory Chair format - explicit match
        ("bookcase & display", "Bookcase"),  # Hickory Chair format
        ("bookcase", "Bookcase"),
        ("display cabinet", "Cabinet"),  # Hickory Chair format
        ("display", "Cabinet"),
        ("mirror", "Mirror"),
        ("accent", "Accent"),
        ("tray", "Accent"),
        ("lighting", "Table Lamp"),
        ("stool", "Stool"),
        ("chest", "Dresser"),
        # Less specific matches last
        ("bed", "Bed"),  # Keep "bed" last so it doesn't match "bedside"
        ("chair", "Chair"),
        ("sofa", "Sofa"),
        ("table", "Table"),  # Generic table match last
    ]

    # Try to match category name against mappings (in order)
    for keyword, product_type in category_to_product_type:
        if keyword in category_lower:
            return product_type

    return None


def categorize_product(product_name: str, category_url: str = None, category_name: str = None) -> dict:
    """
    Categorize a product based on its name, optional category URL, and optional category name.

    Args:
        product_name: Product name
        category_url: Optional category URL
        category_name: Optional category name (e.g., from TypeID metadata)

    Returns:
        Dictionary with 'room_types' (list) and 'product_type' (str or None)
    """
    room_types = []
    product_type = None

    # Extract room type from URL if available
    if category_url:
        room_from_url = extract_room_type_from_url(category_url)
        if room_from_url:
            room_types.append(room_from_url)

    # Try to infer product type from category name first (most reliable)
    if category_name:
        product_type = infer_product_type_from_category_name(category_name)

    # If not found, infer product type from product name
    if not product_type:
        product_type = infer_product_type_from_name(product_name)

    # If no room type from URL, infer from product type
    if not room_types and product_type:
        room_types = infer_room_types_from_product_type(product_type)

    # If still no categorization, mark as Multi-Purpose
    if not room_types:
        room_types = ["Multi-Purpose"]

    return {
        "room_types": room_types,
        "product_type": product_type
    }


if __name__ == "__main__":
    # Test the categorization
    test_cases = [
        ("Odette Fabric Canopy Bed King", "https://www.bernhardt.com/products/luxury-bedroom-furniture/"),
        ("Sofa / Loveseat", None),
        ("acacia wall sconce", None),
        ("Wilkes Side Table", None),
    ]

    for name, url in test_cases:
        result = categorize_product(name, url)
        print(f"\nProduct: {name}")
        if url:
            print(f"URL: {url}")
        print(f"Room Types: {result['room_types']}")
        print(f"Product Type: {result['product_type']}")
