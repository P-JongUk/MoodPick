-- 시청 기록에 미디어 유형·원본 URL (YouTube/Spotify 재생·추천 연동용)
alter table public.watched_content_records
  add column if not exists media_provider text
    check (media_provider is null or media_provider in ('youtube', 'spotify'));

alter table public.watched_content_records
  add column if not exists media_url text;
