"""
Centralized data saver that uploads vendor JSON files to Supabase.
Reads JSON files from the data/ directory and syncs them to the database.

Usage:
    python save_data.py                    # Save all vendors
    python save_data.py hvlgroup           # Save only hvlgroup
    python save_data.py hvlgroup bernhardt # Save multiple specific vendors
"""

import json
import os
import sys
from scrapers.supabase_utils import sync_products_to_supabase

# Configuration
DATA_DIR = "data"

# Map JSON filenames to vendor names
VENDOR_FILES = {
    "hvlgroup": "hvlgroup.json",
    "woodbridgefurniture": "woodbridgefurniture.json",
    "bernhardt": "bernhardt_products.json",
    "hickorychair": "hickorychair_products.json",
    "sherrillfurniture": "sherrillfurniture_products.json",
    "rowefurniture": "rowefurniture_products.json",
}

def load_json_file(file_path):
    """
    Load products from a JSON file

    Args:
        file_path: Path to JSON file

    Returns:
        List of product dictionaries or None if file doesn't exist/invalid
    """
    if not os.path.exists(file_path):
        print(f"  ⚠️  File not found: {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            products = json.load(f)

        if not isinstance(products, list):
            print(f"  ⚠️  Invalid format (not a list): {file_path}")
            return None

        return products

    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON file {file_path}: {e}")
        return None
    except Exception as e:
        print(f"  ✗ Error reading file {file_path}: {e}")
        return None

def save_vendor_data(vendor_name, json_filename):
    """
    Load and save data for a single vendor

    Args:
        vendor_name: Name of the vendor (used as DB identifier)
        json_filename: Name of the JSON file in data/ directory

    Returns:
        Dictionary with sync statistics or None if failed
    """
    file_path = os.path.join(DATA_DIR, json_filename)

    print(f"\n{'=' * 60}")
    print(f"LOADING: {vendor_name.upper()}")
    print(f"{'=' * 60}")
    print(f"File: {file_path}")

    # Load products from JSON
    products = load_json_file(file_path)

    if products is None:
        return None

    if len(products) == 0:
        print(f"  ⚠️  No products found in file")
        return {
            "scraped_count": 0,
            "success_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "deleted_count": 0,
        }

    print(f"  ✓ Loaded {len(products)} products from JSON")

    # Sync to Supabase
    try:
        stats = sync_products_to_supabase(products, vendor_name)
        return {
            "scraped_count": len(products),
            **stats
        }
    except Exception as e:
        print(f"  ✗ Error syncing to Supabase: {e}")
        return None

def main():
    """
    Load vendor JSON files and sync to Supabase.
    Supports command-line arguments to specify which vendors to save.
    """
    # Parse command-line arguments
    vendors_to_save = sys.argv[1:] if len(sys.argv) > 1 else None

    # If specific vendors provided, validate them
    if vendors_to_save:
        invalid_vendors = [v for v in vendors_to_save if v not in VENDOR_FILES]
        if invalid_vendors:
            print(f"❌ Invalid vendor names: {', '.join(invalid_vendors)}")
            print(f"\nValid vendors: {', '.join(VENDOR_FILES.keys())}")
            return

        # Filter to only requested vendors
        vendors_dict = {v: VENDOR_FILES[v] for v in vendors_to_save}
        print("=" * 60)
        print(f"SAVING {len(vendors_dict)} VENDOR(S) TO SUPABASE")
        print("=" * 60)
        print(f"Vendors: {', '.join(vendors_to_save)}")
    else:
        # Save all vendors
        vendors_dict = VENDOR_FILES
        print("=" * 60)
        print("SAVING ALL VENDORS TO SUPABASE")
        print("=" * 60)
        print(f"Vendors: {', '.join(VENDOR_FILES.keys())}")

    total_stats = {
        "vendors_synced": 0,
        "total_products": 0,
        "total_upserted": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "total_deleted": 0,
    }

    for vendor_name, json_filename in vendors_dict.items():
        stats = save_vendor_data(vendor_name, json_filename)

        if stats:
            total_stats["vendors_synced"] += 1
            total_stats["total_products"] += stats.get("scraped_count", 0)
            total_stats["total_upserted"] += stats.get("success_count", 0)
            total_stats["total_skipped"] += stats.get("skipped_count", 0)
            total_stats["total_errors"] += stats.get("error_count", 0)
            total_stats["total_deleted"] += stats.get("deleted_count", 0)

            print(f"✓ {vendor_name} complete")
        else:
            print(f"✗ {vendor_name} failed or skipped")

    # Final summary
    print(f"\n{'=' * 60}")
    print("SYNC COMPLETE - SUMMARY")
    print(f"{'=' * 60}")
    print(f"Vendors synced: {total_stats['vendors_synced']}")
    print(f"Total products loaded: {total_stats['total_products']}")
    print(f"Total upserted: {total_stats['total_upserted']}")
    print(f"Total skipped (unchanged): {total_stats['total_skipped']}")
    print(f"Total errors: {total_stats['total_errors']}")
    print(f"Total deleted: {total_stats['total_deleted']}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
