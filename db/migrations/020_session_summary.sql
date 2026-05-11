-- 멀티턴 상담 대화 하이브리드 요약 저장
-- 임계치(메시지 16건) 초과 세션은 오래된 부분을 요약으로 압축하여 보관한다.
-- summary_until_created_at: 어디 시점까지의 메시지가 summary에 반영됐는지 표시.

alter table public.counseling_sessions
  add column if not exists summary text;

alter table public.counseling_sessions
  add column if not exists summary_until_created_at timestamptz;

comment on column public.counseling_sessions.summary is
  '오래된 대화 누적 요약. 최근 N턴은 원문 유지, 그 이전은 이 컬럼으로 압축.';

comment on column public.counseling_sessions.summary_until_created_at is
  'summary가 반영한 마지막 counseling_history.created_at. 이 시각 이후 메시지는 원문으로 전달됨.';
