-- 008_fix_match_rag_chunks_global_docs.sql
--
-- match_rag_chunks 함수 수정:
-- user_id가 특정 UUID로 필터링될 때도 전역 공유 문서(user_id IS NULL)를 항상 포함.
--
-- 변경 이유:
--   기존 WHERE: filter_user_id IS NULL OR c.user_id = filter_user_id
--   → filter_user_id에 특정 UUID가 오면 user_id=NULL인 매뉴얼 청크가 누락됨.
--   수정 후: user_id IS NULL 조건 추가로 전역 문서 항상 포함.

create or replace function public.match_rag_chunks(
  query_embedding vector(1536),
  match_count int default 5,
  filter_user_id uuid default null
)
returns table (
  chunk_id uuid,
  document_id uuid,
  content text,
  similarity float
)
language sql
stable
as $$
  select
    c.id as chunk_id,
    c.document_id,
    c.content,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.rag_chunks c
  where
    filter_user_id is null          -- 필터 없음 → 전체 반환
    or c.user_id = filter_user_id   -- 유저별 개인 문서
    or c.user_id is null            -- 전역 공유 문서 (매뉴얼 등) 항상 포함
  order by c.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

grant execute on function public.match_rag_chunks(vector, int, uuid) to authenticated;
