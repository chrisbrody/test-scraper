-- Add fixture_type column to direct_furniture table
-- Purpose: Store lighting fixture sub-categorization (e.g., "Chandelier", "Wall Sconce", "Pendant")
-- This is specifically useful for lighting products to provide more granular categorization

-- Add fixture_type column (TEXT, nullable since not all products are lighting)
ALTER TABLE direct_furniture
ADD COLUMN IF NOT EXISTS fixture_type TEXT;

-- Add comment for documentation
COMMENT ON COLUMN direct_furniture.fixture_type IS 'Lighting fixture sub-category (e.g., "Chandelier", "Wall Sconce", "Pendant") - primarily for lighting manufacturers, but could prove useful
';

-- Optional: Add index on fixture_type for filtering
CREATE INDEX IF NOT EXISTS idx_direct_furniture_fixture_type ON direct_furniture(fixture_type) WHERE fixture_type IS NOT NULL;
