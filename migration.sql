-- Migration: torchreid (512-dim) → ResNet50/torchvision (2048-dim)
--
-- Old embeddings are incompatible with new ones:
-- cosine similarity between 512-dim and 2048-dim vectors will always fail.
-- Clear visits from Supabase and delete local SQLite file before restarting.

-- 1. Clear all visit records from Supabase
DELETE FROM visits;

-- 2. Local embeddings (havas_embeddings.db) must be deleted manually:
--    rm ~/Projects/Havas-Pilot/havas_embeddings.db
--
-- After running this migration:
--    python3 main.py   ← will create a fresh havas_embeddings.db automatically
