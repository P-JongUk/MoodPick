-- MoodPick session and content tables for frontend integration

create extension if not exists pgcrypto;

create table if not exists public.counseling_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'active',
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.survey_responses (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.counseling_sessions(id) on delete cascade,
  phase text not null check (phase in ('pre', 'post')),
  question_key text not null,
  emoji_value text not null,
  score double precision not null,
  created_at timestamptz not null default now()
);

create table if not exists public.content_feedback (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.counseling_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  content_id text not null,
  feedback text not null check (feedback in ('like', 'dislike')),
  created_at timestamptz not null default now()
);

create table if not exists public.watched_content_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid references public.counseling_sessions(id) on delete cascade,
  content_id text not null,
  content_title text not null,
  thumbnail_url text,
  watched_at timestamptz not null default now()
);

create index if not exists idx_counseling_sessions_user_id
  on public.counseling_sessions(user_id);

create index if not exists idx_survey_responses_session_id
  on public.survey_responses(session_id);

create index if not exists idx_content_feedback_user_id
  on public.content_feedback(user_id);

create index if not exists idx_watched_content_records_user_id
  on public.watched_content_records(user_id);

alter table public.counseling_sessions enable row level security;
alter table public.survey_responses enable row level security;
alter table public.content_feedback enable row level security;
alter table public.watched_content_records enable row level security;

drop policy if exists "users_manage_own_sessions" on public.counseling_sessions;
create policy "users_manage_own_sessions" on public.counseling_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users_manage_own_survey_responses" on public.survey_responses;
create policy "users_manage_own_survey_responses" on public.survey_responses
  for all
  using (
    exists (
      select 1
      from public.counseling_sessions sessions
      where sessions.id = survey_responses.session_id
      and sessions.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.counseling_sessions sessions
      where sessions.id = survey_responses.session_id
      and sessions.user_id = auth.uid()
    )
  );

drop policy if exists "users_manage_own_content_feedback" on public.content_feedback;
create policy "users_manage_own_content_feedback" on public.content_feedback
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users_manage_own_watched_content" on public.watched_content_records;
create policy "users_manage_own_watched_content" on public.watched_content_records
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
