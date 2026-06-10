-- 023_counseling_session_persona.sql
-- counseling_sessions에 persona 컬럼 추가
-- friend / teacher / expert 중 하나, 기본값 expert (기존 세션은 expert로 백필)

alter table public.counseling_sessions
  add column if not exists persona text not null default 'expert'
    check (persona in ('friend', 'teacher', 'expert'));

create index if not exists idx_counseling_sessions_persona
  on public.counseling_sessions(persona);
