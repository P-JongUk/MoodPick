-- Supabase 공용 DB 등에 한 번에 적용용 (SQL Editor 붙여넣기)
-- 목적: watched_content_records 에 media_url 추가 + media_provider 에 podcast 허용
-- idempotent: 여러 번 실행해도 안전(가능한 범위)

-- 1) media_url (PGRST204: column missing 방지)
alter table public.watched_content_records
  add column if not exists media_url text;

-- 2) media_provider 컬럼이 없으면 추가 (CHECK 없이 — 아래에서 통일)
alter table public.watched_content_records
  add column if not exists media_provider text;

-- 3) media_provider 관련 기존 CHECK 제약 제거 (010의 youtube/spotify 전용 등)
do $$
declare
  r record;
begin
  for r in
    select c.conname
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where c.contype = 'c'
      and n.nspname = 'public'
      and t.relname = 'watched_content_records'
      and pg_get_constraintdef(c.oid) like '%media_provider%'
  loop
    execute format(
      'alter table public.watched_content_records drop constraint if exists %I',
      r.conname
    );
  end loop;
end $$;

-- 4) 통일된 CHECK (youtube / spotify / podcast)
alter table public.watched_content_records
  drop constraint if exists watched_content_records_media_provider_check;

alter table public.watched_content_records
  add constraint watched_content_records_media_provider_check
  check (media_provider is null or media_provider in ('youtube', 'spotify', 'podcast'));
