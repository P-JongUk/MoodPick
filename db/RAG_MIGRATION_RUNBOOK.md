# RAG Migration Runbook

## 목적

MoodPick에서 RAG DB(pgvector)를 적용하기 위한 실행 순서 문서입니다.

## 대상 파일

- `db/migrations/001_initial_schema.sql`
- `db/migrations/002_vector_tables.sql`
- `db/seed_data/001_rag_sample_data.sql`

## 적용 순서

1. Supabase SQL Editor에서 `001_initial_schema.sql`을 먼저 적용합니다.
2. 같은 환경에서 `002_vector_tables.sql`을 적용합니다.
3. `vector` 확장과 `rag_documents`, `rag_chunks` 테이블 생성 여부를 확인합니다.
4. `001_rag_sample_data.sql`을 적용해 샘플 데이터를 넣습니다.
5. 백엔드 `/rag/health`와 `/rag/search`로 동작을 검증합니다.

## 점검 SQL

```sql
-- 확장 확인
select extname from pg_extension where extname = 'vector';

-- 테이블 확인
select to_regclass('public.rag_documents') as rag_documents;
select to_regclass('public.rag_chunks') as rag_chunks;

-- 검색 함수 확인
select proname
from pg_proc
where proname = 'match_rag_chunks';
```

## API 검증

1. `GET /rag/health`
2. `POST /rag/search`
3. `POST /rag/search-by-text`

예시 바디:

```json
{
  "query_embedding": [0.01, 0.01, 0.01, "... 1536차원 ..."],
  "top_k": 3
}
```

주의: 실제 요청에서는 1536차원 임베딩 배열을 전달해야 합니다.

`/rag/search-by-text` 예시 바디:

```json
{
  "query_text": "요즘 스트레스가 너무 심해서 잠을 잘 못 자요",
  "top_k": 3
}
```

주의: 이 엔드포인트는 백엔드 `OPENAI_API_KEY`가 설정되어 있어야 합니다.

## 롤백 가이드(필요 시)

```sql
drop function if exists public.match_rag_chunks(vector, int, uuid);
drop table if exists public.rag_chunks;
drop table if exists public.rag_documents;
drop table if exists public.emotion_embeddings;
```
