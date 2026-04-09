-- Migration 006: AI agent support tables
-- Creates tables needed for the 3-agent counseling pipeline

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Add onboarding_profile to user_profiles
--    Stores concerns, comfort_style, and other onboarding data as JSONB
-- ─────────────────────────────────────────────────────────────────────────────
alter table public.user_profiles
  add column if not exists onboarding_profile jsonb default '{}'::jsonb;

-- Example structure:
-- {
--   "concerns": ["직장", "관계"],
--   "comfort_style": ["음악", "영상"],
--   "age_group": "20s",
--   "preferred_language": "ko"
-- }


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. emotion_records
--    Stores per-message emotion analysis results from the Counselor Agent
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.emotion_records (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  session_id  uuid references public.counseling_sessions(id) on delete cascade,
  emotion     text not null,           -- e.g. "불안", "슬픔", "스트레스"
  intensity   double precision not null check (intensity >= 0 and intensity <= 1),
  raw_message text,                    -- original user message (optional, for analysis)
  created_at  timestamptz not null default now()
);

create index if not exists idx_emotion_records_user_id
  on public.emotion_records(user_id);

create index if not exists idx_emotion_records_session_id
  on public.emotion_records(session_id);

alter table public.emotion_records enable row level security;

drop policy if exists "users_manage_own_emotion_records" on public.emotion_records;
create policy "users_manage_own_emotion_records" on public.emotion_records
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. counseling_history
--    Stores multi-turn conversation messages per session
--    Used by the Counselor Agent to maintain conversation context
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.counseling_history (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references public.counseling_sessions(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  created_at  timestamptz not null default now()
);

create index if not exists idx_counseling_history_session_id
  on public.counseling_history(session_id);

alter table public.counseling_history enable row level security;

drop policy if exists "users_manage_own_counseling_history" on public.counseling_history;
create policy "users_manage_own_counseling_history" on public.counseling_history
  for all
  using (
    exists (
      select 1
      from public.counseling_sessions s
      where s.id = counseling_history.session_id
      and s.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.counseling_sessions s
      where s.id = counseling_history.session_id
      and s.user_id = auth.uid()
    )
  );
