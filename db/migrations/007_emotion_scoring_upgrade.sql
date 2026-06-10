-- 007_emotion_scoring_upgrade.sql
ALTER TABLE emotion_records
ADD COLUMN IF NOT EXISTS emotion_description TEXT,
ADD COLUMN IF NOT EXISTS valence FLOAT,
ADD COLUMN IF NOT EXISTS arousal FLOAT,
ADD COLUMN IF NOT EXISTS va_radius FLOAT;
