/*미반영

create table if not exists public.user_reminder_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  enabled boolean not null default true,
  reminder_time time not null default '22:00:00',
  timezone text not null default 'Asia/Seoul',
  last_sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_reminder_preferences_enabled
  on public.user_reminder_preferences(enabled);

alter table public.user_reminder_preferences enable row level security;

drop policy if exists "users_manage_own_reminder_preferences" on public.user_reminder_preferences;
create policy "users_manage_own_reminder_preferences" on public.user_reminder_preferences
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
