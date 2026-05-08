alter table public.user_profiles
  add column if not exists gender varchar(32),
  add column if not exists birth_year integer;

