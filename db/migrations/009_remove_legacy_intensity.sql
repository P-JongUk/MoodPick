-- 009_remove_legacy_intensity.sql
-- Remove the legacy `intensity` column from emotion_records.
-- Rationale: The VA model (valence, arousal, va_radius) was introduced in migration 007.
-- `va_radius` stores the confidence_radius from the Russell circumplex lookup
-- (EMOTION_VA_MAP in ai/tools/emotion_va_map.py). It represents the spatial extent
-- of an emotion cluster on the VA plane (0.15~0.30) — NOT sqrt(V²+A²).
-- The legacy `intensity` column was a GPT-estimated 0~1 value redundant with the
-- VA coordinates themselves. The recommendation-time strength signal is now
-- computed at runtime in counselor.py's _build_emotion_score() and persisted only
-- in recommendation_log.intensity (a separate concept; "care urgency" derived from
-- valence/arousal via min(1, max(0,-V)*0.6 + |A|*0.4), not equal to va_radius).
ALTER TABLE public.emotion_records
DROP COLUMN IF EXISTS intensity;
