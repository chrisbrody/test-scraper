import os
from supabase import create_client, Client
from dotenv import load_dotenv

def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client using environment variables
    """
    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_existing_products(vendor: str) -> dict:
    """
    Get existing products from database with their updated_at timestamps.

    Args:
        vendor: Vendor name

    Returns:
        Dictionary mapping SKU to product data (including updated_at)
    """
    supabase = get_supabase_client()

    try:
        result = supabase.table("direct_furniture").select("*").eq("vendor", vendor).execute()
        # Return as dict with SKU as key for easy lookup
        return {product['sku']: product for product in result.data}
    except Exception as e:
        print(f"Warning: Could not fetch existing products: {e}")
        return {}


def product_needs_update(new_product: dict, existing_product: dict) -> bool:
    """
    Check if a product needs to be updated by comparing key fields.

    Args:
        new_product: New product data from scraper
        existing_product: Existing product data from database

    Returns:
        True if product needs update, False otherwise
    """
    # Fields to compare (ignore timestamps and IDs)
    compare_fields = ['name', 'img_url', 'product_url', 'price', 'in_stock', 'room_types', 'product_type', 'fixture_type']

    for field in compare_fields:
        new_value = new_product.get(field)
        existing_value = existing_product.get(field)

        # Handle None/empty comparisons
        if new_value != existing_value:
            return True

    return False


def sync_products_to_supabase(products: list, vendor: str, batch_size: int = 100, skip_unchanged: bool = True) -> dict:
    """
    Sync products to Supabase for a specific vendor.
    Upserts all products in batches and deletes ones no longer on the website.

    Args:
        products: List of product dictionaries with keys: name, sku, img_url, product_url, price, in_stock
        vendor: Vendor name (e.g., "hvlgroup", "woodbridgefurniture", "bernhardt")
        batch_size: Number of products to upsert per batch (default: 100)
        skip_unchanged: If True, skip products that haven't changed (default: True)

    Returns:
        Dictionary with sync statistics: success_count, error_count, deleted_count, skipped_count
    """
    supabase = get_supabase_client()

    print(f"\n{'='*50}")
    print(f"Syncing {len(products)} products to Supabase for vendor: {vendor}...")
    print(f"Batch size: {batch_size}")
    print(f"Skip unchanged: {skip_unchanged}")
    print(f"{'='*50}")

    # Get existing products if we're skipping unchanged
    existing_products = {}
    if skip_unchanged:
        print("\nFetching existing products from database...")
        existing_products = get_existing_products(vendor)
        print(f"Found {len(existing_products)} existing products in database")

    # Get all SKUs from scraped products
    scraped_skus = {product['sku'] for product in products}

    # Upsert all products in batches
    success_count = 0
    error_count = 0
    skipped_count = 0
    total_batches = (len(products) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(products))
        batch = products[start_idx:end_idx]

        print(f"\nProcessing batch {batch_num + 1}/{total_batches} ({len(batch)} products)...")

        for product in batch:
            try:
                sku = product['sku']

                # Check if product needs update
                if skip_unchanged and sku in existing_products:
                    if not product_needs_update(product, existing_products[sku]):
                        skipped_count += 1
                        print(f"⊘ Skipped (unchanged): {product['name']} ({sku})")
                        continue

                # Add vendor to product data
                product_data = {**product, "vendor": vendor}

                # Use upsert to handle duplicates (will update if vendor+SKU already exists)
                result = supabase.table("direct_furniture").upsert(
                    product_data,
                    on_conflict="vendor,sku"
                ).execute()

                success_count += 1
                if sku in existing_products:
                    print(f"↻ Updated: {product['name']} ({sku})")
                else:
                    print(f"+ Added: {product['name']} ({sku})")

            except Exception as e:
                error_count += 1
                print(f"✗ Error upserting {product['sku']}: {e}")

    # Delete products that are no longer on the website (only for this vendor)
    print(f"\n{'='*50}")
    print(f"Removing {vendor} products no longer on website...")
    print(f"{'='*50}")

    deleted_count = 0
    try:
        # Get all existing SKUs from database for this vendor
        existing_products = supabase.table("direct_furniture").select("sku").eq("vendor", vendor).execute()
        existing_skus = {product['sku'] for product in existing_products.data}

        # Find SKUs to delete (in database but not in scraped data)
        skus_to_delete = existing_skus - scraped_skus

        if skus_to_delete:
            for sku in skus_to_delete:
                try:
                    supabase.table("direct_furniture").delete().eq("vendor", vendor).eq("sku", sku).execute()
                    print(f"✓ Deleted: {sku}")
                    deleted_count += 1
                except Exception as e:
                    print(f"✗ Error deleting {sku}: {e}")
            print(f"\nDeleted {deleted_count} discontinued products")
        else:
            print("No products to delete")

    except Exception as e:
        print(f"Error checking for products to delete: {e}")

    print(f"\n{'='*50}")
    print(f"Sync complete!")
    print(f"Added/Updated: {success_count}")
    print(f"Skipped (unchanged): {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Deleted: {deleted_count}")
    print(f"{'='*50}")

    return {
        "success_count": success_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "deleted_count": deleted_count
    }
