-- db/migrations/016_recommendation_log_ambiguity.sql
-- Add coordinate-based emotion ambiguity signal columns to recommendation_log.
-- Rationale: `va_radius` (in emotion_records) is a static cluster-level radius from
-- EMOTION_VA_MAP and cannot tell whether the user's actual VA coordinate sits at the
-- cluster center or near a boundary. We compute a dynamic ambiguity at recommendation
-- time via compute_emotion_ambiguity() (top-2 normalized-distance ratio) and persist
-- both the score and the secondary label that was passed to the search-query LLM,
-- enabling later analysis of whether ambiguity-aware queries improved outcomes.
ALTER TABLE public.recommendation_log
  ADD COLUMN IF NOT EXISTS ambiguity         real,
  ADD COLUMN IF NOT EXISTS secondary_emotion text;
