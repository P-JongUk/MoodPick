-- Sample data for MoodPick RAG tables
-- Run after applying 002_vector_tables.sql

with seeded_user as (
  select id as user_id
  from auth.users
  order by created_at asc
  limit 1
), inserted_doc as (
  insert into public.rag_documents (
    user_id,
    source_type,
    source_ref,
    title,
    metadata
  )
  select
    su.user_id,
    'guide',
    'seed-001',
    '초기 RAG 샘플 문서',
    '{"lang":"ko","topic":"stress"}'::jsonb
  from seeded_user su
  returning id, user_id
)
insert into public.rag_chunks (
  document_id,
  user_id,
  chunk_index,
  content,
  token_count,
  embedding
)
select
  d.id,
  d.user_id,
  gs.idx,
  case
    when gs.idx = 0 then '스트레스가 높을 때는 호흡 조절과 짧은 산책이 도움이 됩니다.'
    when gs.idx = 1 then '감정을 즉시 판단하지 말고 이름 붙이기부터 시작해 보세요.'
    else '수면 리듬을 먼저 안정화하면 감정 기복 완화에 도움이 됩니다.'
  end,
  40,
  (
    select array_agg((random() * 0.05)::real)
    from generate_series(1, 1536)
  )::vector
from inserted_doc d
cross join (values (0), (1), (2)) as gs(idx);
