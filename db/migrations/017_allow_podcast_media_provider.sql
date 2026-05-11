-- Allow podcast in watched content media provider
-- 기존 010_watched_content_media.sql에서는 youtube/spotify만 허용합니다.
-- podcast 오디오 재생을 위해 provider 값 확장을 허용합니다.

do $$
begin
  -- Drop existing CHECK constraint if it exists (name can vary by Postgres)
  if exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where c.contype = 'c'
      and n.nspname = 'public'
      and t.relname = 'watched_content_records'
      and pg_get_constraintdef(c.oid) like '%media_provider%'
  ) then
    -- Best-effort: remove all media_provider-related CHECK constraints
    execute (
      select string_agg(format('alter table public.watched_content_records drop constraint %I;', c.conname), ' ')
      from pg_constraint c
      join pg_class t on t.oid = c.conrelid
      join pg_namespace n on n.oid = t.relnamespace
      where c.contype = 'c'
        and n.nspname = 'public'
        and t.relname = 'watched_content_records'
        and pg_get_constraintdef(c.oid) like '%media_provider%'
    );
  end if;
exception when others then
  -- ignore; constraint may not exist or permissions may differ
  null;
end $$;

alter table public.watched_content_records
  add constraint watched_content_records_media_provider_check
  check (media_provider is null or media_provider in ('youtube', 'spotify', 'podcast'));

