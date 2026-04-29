-- Migration 014: per-photo selection reasoning for evidence photos.
-- Stores Sonnet's Step 1 description for each evidence photo so the
-- report UI can show a hover tooltip explaining why each photo was chosen.
ALTER TABLE requirement_results ADD COLUMN IF NOT EXISTS photo_captions JSONB DEFAULT '{}';
