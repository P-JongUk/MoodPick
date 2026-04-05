-- MoodPick frontend verification seed (development only)
-- Usage:
-- 1) Replace target_user_id in the _seed_params insert statement with an existing auth.users.id UUID.
-- 2) Run in Supabase SQL Editor.
-- 3) Re-runnable: existing rows with the same seed content_id/source are cleaned up first.

begin;

create temporary table if not exists _seed_params (
  target_user_id uuid not null,
  seed_now timestamptz not null
) on commit drop;

truncate table _seed_params;

insert into _seed_params (target_user_id, seed_now)
values ('c7dcdbd4-f103-4707-a8ad-f0845fcd4d36'::uuid, now()); -- 해당 uid를 바꿔서 시드 데이터 유저 변경 가능

with params as (
  select
    target_user_id,
    seed_now as ts_now
  from _seed_params
),
seed_sessions as (
  insert into public.counseling_sessions (user_id, status, started_at, ended_at, created_at)
  select
    p.target_user_id,
    s.status,
    p.ts_now - s.start_offset,
    case when s.status = 'ended' then p.ts_now - s.end_offset else null end,
    p.ts_now - s.start_offset
  from params p
  cross join (
    values
      ('ended'::text, interval '5 days', interval '5 days - 35 minutes'),
      ('ended'::text, interval '3 days', interval '3 days - 28 minutes'),
      ('active'::text, interval '10 minutes', interval '0 minutes')
  ) as s(status, start_offset, end_offset)
  returning id, status, started_at
),
session_ordered as (
  select
    id,
    status,
    started_at,
    row_number() over (order by started_at asc) as rn
  from seed_sessions
),
seed_surveys as (
  insert into public.survey_responses (session_id, phase, question_key, emoji_value, score, created_at)
  select
    so.id,
    v.phase,
    v.question_key,
    v.emoji_value,
    v.score,
    so.started_at + v.time_offset
  from session_ordered so
  join (
    values
      (1, 'pre'::text,  'mood_general'::text, 'low'::text,    2::double precision, interval '2 minutes'),
      (1, 'pre'::text,  'energy_level'::text, 'low'::text,    2::double precision, interval '3 minutes'),
      (1, 'pre'::text,  'stress_level'::text, 'bad'::text,    1::double precision, interval '4 minutes'),
      (1, 'post'::text, 'mood_general'::text, 'neutral'::text,3::double precision, interval '30 minutes'),
      (1, 'post'::text, 'energy_level'::text, 'neutral'::text,3::double precision, interval '31 minutes'),
      (1, 'post'::text, 'stress_level'::text, 'low'::text,    2::double precision, interval '32 minutes'),

      (2, 'pre'::text,  'mood_general'::text, 'neutral'::text,3::double precision, interval '2 minutes'),
      (2, 'pre'::text,  'energy_level'::text, 'good'::text,   4::double precision, interval '3 minutes'),
      (2, 'pre'::text,  'stress_level'::text, 'neutral'::text,3::double precision, interval '4 minutes'),
      (2, 'post'::text, 'mood_general'::text, 'good'::text,   4::double precision, interval '24 minutes'),
      (2, 'post'::text, 'energy_level'::text, 'great'::text,  5::double precision, interval '25 minutes'),
      (2, 'post'::text, 'stress_level'::text, 'good'::text,   4::double precision, interval '26 minutes'),

      (3, 'pre'::text,  'mood_general'::text, 'good'::text,   4::double precision, interval '1 minutes'),
      (3, 'pre'::text,  'energy_level'::text, 'neutral'::text,3::double precision, interval '2 minutes'),
      (3, 'pre'::text,  'stress_level'::text, 'low'::text,    2::double precision, interval '3 minutes')
  ) as v(rn, phase, question_key, emoji_value, score, time_offset)
    on v.rn = so.rn
  returning id
)
select count(*) as inserted_survey_rows from seed_surveys;

-- Clean up previous seed content rows for idempotency.
delete from public.content_feedback
where user_id = (select target_user_id from _seed_params)
  and content_id like 'seed-dev-%';

delete from public.watched_content_records
where user_id = (select target_user_id from _seed_params)
  and content_id like 'seed-dev-%';

with params as (
  select
    target_user_id,
    seed_now as ts_now
  from _seed_params
),
recent_sessions as (
  select id, row_number() over (order by started_at desc) as rn
  from public.counseling_sessions
  where user_id = (select target_user_id from params)
  order by started_at desc
  limit 3
),
seed_contents as (
  insert into public.watched_content_records (user_id, session_id, content_id, content_title, thumbnail_url, watched_at)
  select
    p.target_user_id,
    rs.id,
    c.content_id,
    c.content_title,
    c.thumbnail_url,
    p.ts_now - c.offset_time
  from params p
  join recent_sessions rs on true
  join (
    values
      (1, 'seed-dev-fireplace'::text, '우울함을 달래주는 따뜻한 장작 소리'::text, null::text, interval '2 days'),
      (2, 'seed-dev-rain-meditation'::text, '빗소리와 함께하는 명상 음악'::text, null::text, interval '1 day'),
      (3, 'seed-dev-forest'::text, '숲속 새소리 1시간'::text, null::text, interval '2 hours')
  ) as c(rn, content_id, content_title, thumbnail_url, offset_time)
    on c.rn = rs.rn
  returning session_id, content_id
),
seed_feedback as (
  insert into public.content_feedback (session_id, user_id, content_id, feedback, created_at)
  select
    sc.session_id,
    p.target_user_id,
    sc.content_id,
    case when sc.content_id = 'seed-dev-rain-meditation' then 'dislike' else 'like' end,
    p.ts_now - interval '30 minutes'
  from seed_contents sc
  cross join params p
  returning id
)
select count(*) as inserted_feedback_rows from seed_feedback;

-- Reminder preference/log seed only if those tables are present.
do $$
declare
  v_user uuid;
begin
  select target_user_id into v_user
  from _seed_params
  limit 1;

  if v_user is null then
    raise exception 'seed target_user_id is required';
  end if;

  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'user_profiles'
  ) then
    insert into public.user_profiles (user_id, display_name, updated_at)
    values (v_user, '무드픽 테스트유저', now())
    on conflict (user_id)
    do update set
      display_name = excluded.display_name,
      updated_at = now();
  end if;

  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'user_reminder_preferences'
  ) then
    insert into public.user_reminder_preferences (user_id, enabled, reminder_time, timezone, last_sent_at, updated_at)
    values (v_user, true, '22:00:00'::time, 'Asia/Seoul', now() - interval '1 day', now())
    on conflict (user_id)
    do update set
      enabled = excluded.enabled,
      reminder_time = excluded.reminder_time,
      timezone = excluded.timezone,
      updated_at = now();
  end if;

  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'reminder_dispatch_logs'
  ) then
    delete from public.reminder_dispatch_logs
    where user_id = v_user
      and source like 'seed-dev-%';

    insert into public.reminder_dispatch_logs (user_id, status, source, detail, created_at)
    values
      (v_user, 'sent', 'seed-dev-manual', 'seed dispatch success sample', now() - interval '1 day'),
      (v_user, 'failed', 'seed-dev-manual', 'seed dispatch failed sample', now() - interval '12 hours');
  end if;
end $$;

commit;
