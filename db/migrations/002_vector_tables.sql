-- MoodPick RAG/Vector schema migration

create extension if not exists vector;

-- Emotion/context embeddings (session-level)
create table if not exists public.emotion_embeddings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid references public.counseling_sessions(id) on delete cascade,
  source_text text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

-- RAG documents metadata
create table if not exists public.rag_documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  source_type text not null default 'session',
  source_ref text,
  title text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- RAG chunks and embeddings
create table if not exists public.rag_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.rag_documents(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  token_count int,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_emotion_embeddings_user_id
  on public.emotion_embeddings(user_id);

create index if not exists idx_rag_documents_user_id
  on public.rag_documents(user_id);

create index if not exists idx_rag_chunks_document_id
  on public.rag_chunks(document_id);

create index if not exists idx_rag_chunks_user_id
  on public.rag_chunks(user_id);

create index if not exists idx_emotion_embeddings_embedding
  on public.emotion_embeddings using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index if not exists idx_rag_chunks_embedding
  on public.rag_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

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
  where filter_user_id is null or c.user_id = filter_user_id
  order by c.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

alter table public.emotion_embeddings enable row level security;
alter table public.rag_documents enable row level security;
alter table public.rag_chunks enable row level security;

drop policy if exists "users_manage_own_emotion_embeddings" on public.emotion_embeddings;
create policy "users_manage_own_emotion_embeddings" on public.emotion_embeddings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users_manage_own_rag_documents" on public.rag_documents;
create policy "users_manage_own_rag_documents" on public.rag_documents
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users_manage_own_rag_chunks" on public.rag_chunks;
create policy "users_manage_own_rag_chunks" on public.rag_chunks
  for all
  using (
    auth.uid() = user_id
    or exists (
      select 1
      from public.rag_documents docs
      where docs.id = rag_chunks.document_id
      and docs.user_id = auth.uid()
    )
  )
  with check (
    auth.uid() = user_id
    or exists (
      select 1
      from public.rag_documents docs
      where docs.id = rag_chunks.document_id
      and docs.user_id = auth.uid()
    )
  );

grant execute on function public.match_rag_chunks(vector, int, uuid) to authenticated;
