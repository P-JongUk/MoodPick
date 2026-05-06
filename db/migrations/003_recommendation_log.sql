-- db/migrations/003_recommendation_log.sql
create table if not exists public.recommendation_log (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id),
  session_id     uuid not null references public.counseling_sessions(id),
  search_query   text not null,
  video_id       text,
  video_title    text,
  reason         text,
  emotion        text,
  intensity      real,
  candidate_pool jsonb,                   -- 5~10개 후보의 video_id + score
  selected_score real,                    -- 선정된 영상의 하이브리드 점수
  strategy_version text,                  -- "v2.1" 등
  created_at     timestamptz not null default now(),
  watched_at     timestamptz,
  feedback       text                     -- "like" | "dislike" | null
);

create index if not exists idx_reclog_user_session on public.recommendation_log (user_id, session_id);
create index if not exists idx_reclog_user_created on public.recommendation_log (user_id, created_at desc);
