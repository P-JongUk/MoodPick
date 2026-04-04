/*미반영

create table if not exists public.reminder_dispatch_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  status text not null check (status in ('sent', 'failed')),
  source text not null,
  detail text,
  created_at timestamptz not null default now()
);

create index if not exists idx_reminder_dispatch_logs_user_id
  on public.reminder_dispatch_logs(user_id);

create index if not exists idx_reminder_dispatch_logs_created_at
  on public.reminder_dispatch_logs(created_at desc);

alter table public.reminder_dispatch_logs enable row level security;

drop policy if exists "users_read_own_reminder_dispatch_logs" on public.reminder_dispatch_logs;
create policy "users_read_own_reminder_dispatch_logs" on public.reminder_dispatch_logs
  for select using (auth.uid() = user_id);
