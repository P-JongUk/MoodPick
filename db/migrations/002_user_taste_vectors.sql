-- db/migrations/002_user_taste_vectors.sql
create table if not exists public.user_taste_vectors (
  user_id        uuid primary key references auth.users(id),
  embedding      vector(1536) not null,
  embedding_model text not null default 'text-embedding-3-small',
  source_count   int not null,            -- 몇 개 좋아요로 만들었는지
  strategy       text not null,           -- "time_weighted_avg" | "centroid" | ...
  updated_at     timestamptz not null default now()
);
