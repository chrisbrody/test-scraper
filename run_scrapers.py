"""
Centralized scraper runner that executes all vendor scrapers sequentially.
Allows easy control over which scrapers to run and batch size limits.
"""

from scrapers import hvlgroup, woodbridgefurniture, bernhardt, hickorychair, sherrillfurniture, rowefurniture

# Configuration
SCRAPERS = {
    "hvlgroup": {
        "enabled": True,
        "scraper": hvlgroup.scrape,
        # Note: hvlgroup uses room_configs internally, no pages param needed
        "async": False,
    },
    "woodbridgefurniture": {
        "enabled": True,
        "scraper": woodbridgefurniture.scrape,
        "pages": 1,  # Number of pages to scrape
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
    "rowefurniture": {
        "enabled": True,
        "scraper": rowefurniture.scrape,
    },
}

# Global settings
MAX_PRODUCTS_PER_BATCH = 500  # Limit products per vendor before syncing

def main():
    """
    Run all enabled scrapers sequentially
    """
    print("=" * 60)
    print("STARTING MULTI-VENDOR SCRAPER")
    print("=" * 60)

    total_stats = {
        "vendors_scraped": 0,
        "total_products": 0,
        "total_upserted": 0,
        "total_errors": 0,
        "total_deleted": 0,
    }

    for vendor_name, config in SCRAPERS.items():
        if not config["enabled"]:
            print(f"\n⏭️  Skipping {vendor_name} (disabled)")
            continue

        print(f"\n{'=' * 60}")
        print(f"SCRAPING: {vendor_name.upper()}")
        print(f"{'=' * 60}")

        try:
            # Run scraper with configured settings
            # Only pass num_pages if it exists in config (not all scrapers use it)
            scraper_kwargs = {"max_products": MAX_PRODUCTS_PER_BATCH}
            if "pages" in config:
                scraper_kwargs["num_pages"] = config["pages"]

            stats = config["scraper"](**scraper_kwargs)

            # Update totals
            total_stats["vendors_scraped"] += 1
            total_stats["total_products"] += stats.get("scraped_count", 0)
            total_stats["total_upserted"] += stats.get("success_count", 0)
            total_stats["total_errors"] += stats.get("error_count", 0)
            total_stats["total_deleted"] += stats.get("deleted_count", 0)

            print(f"✓ {vendor_name} complete")

        except Exception as e:
            print(f"✗ Error running {vendor_name} scraper: {e}")
            continue

    # Final summary
    print(f"\n{'=' * 60}")
    print("SCRAPING COMPLETE - SUMMARY")
    print(f"{'=' * 60}")
    print(f"Vendors scraped: {total_stats['vendors_scraped']}")
    print(f"Total products scraped: {total_stats['total_products']}")
    print(f"Total upserted: {total_stats['total_upserted']}")
    print(f"Total errors: {total_stats['total_errors']}")
    print(f"Total deleted: {total_stats['total_deleted']}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
