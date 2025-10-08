-- Add price and in_stock columns to direct_furniture table
-- Purpose: Store pricing and availability information from vendor JSON-LD data

-- Add price column (NUMERIC to store decimal values, nullable since not all products have price)
ALTER TABLE direct_furniture
ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2);

-- Drop existing in_stock column if it exists (changing from BOOLEAN to TEXT)
ALTER TABLE direct_furniture
DROP COLUMN IF EXISTS in_stock;

-- Add in_stock column as TEXT to store availability messages
-- Examples: "In stock", "On the way! Arriving 11/1/2025", "http://schema.org/InStock", etc.
ALTER TABLE direct_furniture
ADD COLUMN in_stock TEXT;

-- Add comments for documentation
COMMENT ON COLUMN direct_furniture.price IS 'Product price from vendor (may be null if not available)';
COMMENT ON COLUMN direct_furniture.in_stock IS 'Product availability status as text (e.g., "In stock", "Arriving 11/1/2025", or null if unknown)';

-- Optional: Add index on price for filtering/sorting
CREATE INDEX IF NOT EXISTS idx_direct_furniture_price ON direct_furniture(price) WHERE price IS NOT NULL;

-- Optional: Add index on in_stock for availability filtering
CREATE INDEX IF NOT EXISTS idx_direct_furniture_in_stock ON direct_furniture(in_stock) WHERE in_stock IS NOT NULL;
