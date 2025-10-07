-- Create direct_furniture table
-- Purpose: Multi-vendor product catalog for interior designers to search and discover
-- furniture products from various direct-to-trade manufacturers. Enables designers
-- to find products by name, SKU, vendor, or browse across multiple vendors in one place.
CREATE TABLE IF NOT EXISTS direct_furniture (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor TEXT NOT NULL,
    name TEXT,
    sku TEXT NOT NULL,
    img_url TEXT,
    product_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vendor, sku)  -- SKU must be unique per vendor
);

COMMENT ON TABLE direct_furniture IS 'Multi-vendor furniture catalog for interior designers to search products from direct-to-trade manufacturers';
COMMENT ON COLUMN direct_furniture.vendor IS 'Manufacturer/vendor name (e.g., hvlgroup, woodbridgefurniture)';
COMMENT ON COLUMN direct_furniture.sku IS 'Product SKU - unique within each vendor';
COMMENT ON COLUMN direct_furniture.name IS 'Product name for designer search';
COMMENT ON COLUMN direct_furniture.img_url IS 'Product image URL for visual reference';
COMMENT ON COLUMN direct_furniture.product_url IS 'Direct link to product on vendor website';

-- Create index on vendor for faster lookups
CREATE INDEX IF NOT EXISTS idx_direct_furniture_vendor ON direct_furniture(vendor);

-- Create index on SKU for faster lookups
CREATE INDEX IF NOT EXISTS idx_direct_furniture_sku ON direct_furniture(sku);

-- Create composite index for vendor + sku queries
CREATE INDEX IF NOT EXISTS idx_direct_furniture_vendor_sku ON direct_furniture(vendor, sku);

-- Create index on name for search
CREATE INDEX IF NOT EXISTS idx_direct_furniture_name ON direct_furniture(name);

-- Enable Row Level Security
ALTER TABLE direct_furniture ENABLE ROW LEVEL SECURITY;

-- Create policy to allow public read access
CREATE POLICY "Allow public read access"
    ON direct_furniture
    FOR SELECT
    TO public
    USING (true);

-- Create policy to allow service role insert (for scripts/backend)
CREATE POLICY "Allow service role insert"
    ON direct_furniture
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- Create policy to allow service role update
CREATE POLICY "Allow service role update"
    ON direct_furniture
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Create policy to allow service role delete
CREATE POLICY "Allow service role delete"
    ON direct_furniture
    FOR DELETE
    TO service_role
    USING (true);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_direct_furniture_updated_at
    BEFORE UPDATE ON direct_furniture
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
