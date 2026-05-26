-- Migration 022: Backfill public.user_profiles.onboarding_profile from
-- auth.users.raw_user_meta_data, and split legacy comfort_style in auth metadata.
--
-- 배경:
--   frontend는 auth.users.raw_user_meta_data에만 저장해왔고 public.user_profiles의
--   onboarding_profile 컬럼은 한 번도 채워진 적이 없음. AI 백엔드(get_user_profile)는
--   이 컬럼을 읽으므로 톤 블록·content_preference 분기·콜드스타트 임베딩이 작동하지 않음.
--   이 마이그레이션은 (1) auth.users 안의 legacy comfort_style을 split하고,
--   (2) auth metadata를 public.user_profiles로 백필한다.
--
-- 권한: auth.users UPDATE는 service_role 필요. Supabase SQL Editor는 보통 service_role로 실행됨.

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1. auth.users.raw_user_meta_data.onboarding_profile.comfort_style 을
--         counseling_tone/content_preference 로 split.
-- ─────────────────────────────────────────────────────────────────────────────
update auth.users
set raw_user_meta_data = jsonb_set(
  raw_user_meta_data,
  '{onboarding_profile}',
  jsonb_set(
    jsonb_set(
      (raw_user_meta_data -> 'onboarding_profile') - 'comfort_style',
      '{counseling_tone}',
      coalesce(
        (
          select jsonb_agg(elem)
          from jsonb_array_elements_text(raw_user_meta_data #> '{onboarding_profile,comfort_style}') elem
          where elem in ('listen', 'advice')
        ),
        '[]'::jsonb
      )
    ),
    '{content_preference}',
    coalesce(
      (
        select jsonb_agg(elem)
        from jsonb_array_elements_text(raw_user_meta_data #> '{onboarding_profile,comfort_style}') elem
        where elem in ('music', 'video')
      ),
      '[]'::jsonb
    )
  )
)
where raw_user_meta_data #> '{onboarding_profile,comfort_style}' is not null;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2. auth.users.raw_user_meta_data.onboarding_profile 을
--         public.user_profiles.onboarding_profile 로 백필.
--         이미 채워진(non-empty) 행은 덮어쓰지 않음.
--         user_profiles 행이 없으면 display_name/gender/birth_year도 함께 채움.
-- ─────────────────────────────────────────────────────────────────────────────
insert into public.user_profiles (
  user_id,
  display_name,
  gender,
  birth_year,
  onboarding_profile,
  updated_at
)
select
  au.id,
  coalesce(
    nullif(trim(au.raw_user_meta_data ->> 'display_name'), ''),
    split_part(au.email, '@', 1),
    au.id::text
  ) as display_name,
  nullif(au.raw_user_meta_data ->> 'gender', '') as gender,
  nullif(au.raw_user_meta_data ->> 'birth_year', '')::int as birth_year,
  au.raw_user_meta_data -> 'onboarding_profile' as onboarding_profile,
  now() as updated_at
from auth.users au
where (au.raw_user_meta_data -> 'onboarding_profile') is not null
  and (au.raw_user_meta_data -> 'onboarding_profile') <> '{}'::jsonb
on conflict (user_id) do update
set
  onboarding_profile = case
    when public.user_profiles.onboarding_profile is null
      or public.user_profiles.onboarding_profile = '{}'::jsonb
    then excluded.onboarding_profile
    else public.user_profiles.onboarding_profile
  end,
  updated_at = now();
