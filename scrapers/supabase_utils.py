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

def sync_products_to_supabase(products: list, vendor: str, batch_size: int = 100) -> dict:
    """
    Sync products to Supabase for a specific vendor.
    Upserts all products in batches and deletes ones no longer on the website.

    Args:
        products: List of product dictionaries with keys: name, sku, img_url, product_url
        vendor: Vendor name (e.g., "hvlgroup", "woodbridgefurniture")
        batch_size: Number of products to upsert per batch (default: 100)

    Returns:
        Dictionary with sync statistics: success_count, error_count, deleted_count
    """
    supabase = get_supabase_client()

    print(f"\n{'='*50}")
    print(f"Syncing {len(products)} products to Supabase for vendor: {vendor}...")
    print(f"Batch size: {batch_size}")
    print(f"{'='*50}")

    # Get all SKUs from scraped products
    scraped_skus = {product['sku'] for product in products}

    # Upsert all products in batches
    success_count = 0
    error_count = 0
    total_batches = (len(products) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(products))
        batch = products[start_idx:end_idx]

        print(f"\nProcessing batch {batch_num + 1}/{total_batches} ({len(batch)} products)...")

        for product in batch:
            try:
                # Add vendor to product data
                product_data = {**product, "vendor": vendor}

                # Use upsert to handle duplicates (will update if vendor+SKU already exists)
                result = supabase.table("direct_furniture").upsert(
                    product_data,
                    on_conflict="vendor,sku"
                ).execute()

                success_count += 1
                print(f"✓ Upserted: {product['name']} ({product['sku']})")

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
    print(f"Upserted: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Deleted: {deleted_count}")
    print(f"{'='*50}")

    return {
        "success_count": success_count,
        "error_count": error_count,
        "deleted_count": deleted_count
    }
