-- 세션 단위 명상/오디오 추천 형식 선호 (guided vs music_only)

alter table public.counseling_sessions
  add column if not exists meditation_audio_format text;

alter table public.counseling_sessions
  drop constraint if exists counseling_sessions_meditation_audio_format_check;

alter table public.counseling_sessions
  add constraint counseling_sessions_meditation_audio_format_check
  check (
    meditation_audio_format is null
    or meditation_audio_format in ('guided', 'music_only')
  );

comment on column public.counseling_sessions.meditation_audio_format is
  '명상·오디오 추천 시 선호: guided(가이드형) | music_only(말 없는 음악·BGM)';
