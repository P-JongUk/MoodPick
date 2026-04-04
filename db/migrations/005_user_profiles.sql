create table if not exists public.user_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_profiles_display_name
  on public.user_profiles(display_name);

alter table public.user_profiles enable row level security;

drop policy if exists "users_manage_own_profile" on public.user_profiles;
create policy "users_manage_own_profile" on public.user_profiles
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
