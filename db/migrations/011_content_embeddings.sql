-- db/migrations/011_content_embeddings.sql
create table if not exists public.content_embeddings (
  content_id     text primary key,        -- YouTube video_id
  source_text    text not null,           -- 임베딩 입력 (title + description 일부)
  embedding      vector(1536) not null,   -- OpenAI text-embedding-3-small
  embedding_model text not null default 'text-embedding-3-small',
  metadata       jsonb,                   -- channel_id, duration, view_count 등
  created_at     timestamptz not null default now()
);

create index if not exists idx_content_emb_model on public.content_embeddings (embedding_model);
create index if not exists idx_content_emb_vec on public.content_embeddings
  using hnsw (embedding vector_cosine_ops);
