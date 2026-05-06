-- 009_remove_legacy_intensity.sql
-- Remove the legacy `intensity` column from emotion_records.
-- Rationale: The VA model (valence, arousal, va_radius) was introduced in migration 007
-- and provides a mathematically grounded measure of emotion strength (va_radius = sqrt(V²+A²)).
-- The `intensity` field was a GPT-estimated value from the pre-VA era and is now redundant.
ALTER TABLE public.emotion_records
DROP COLUMN IF EXISTS intensity;
