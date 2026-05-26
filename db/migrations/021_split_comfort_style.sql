-- Migration 021: Split onboarding_profile.comfort_style into
-- counseling_tone (listen/advice) and content_preference (music/video).
--
-- Before:
--   { "concerns": [...], "comfort_style": ["listen", "music"], ... }
-- After:
--   { "concerns": [...], "counseling_tone": ["listen"], "content_preference": ["music"], ... }

update public.user_profiles
set onboarding_profile = jsonb_set(
  jsonb_set(
    onboarding_profile - 'comfort_style',
    '{counseling_tone}',
    coalesce(
      (
        select jsonb_agg(elem)
        from jsonb_array_elements_text(onboarding_profile -> 'comfort_style') elem
        where elem in ('listen', 'advice')
      ),
      '[]'::jsonb
    )
  ),
  '{content_preference}',
  coalesce(
    (
      select jsonb_agg(elem)
      from jsonb_array_elements_text(onboarding_profile -> 'comfort_style') elem
      where elem in ('music', 'video')
    ),
    '[]'::jsonb
  )
)
where onboarding_profile ? 'comfort_style';
