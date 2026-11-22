-- Execute este script no SQL Editor do seu projeto gratuito no Supabase
-- Ele cria a tabela de dados por usuário e ativa o isolamento por Row Level Security (RLS).

create table if not exists public.tracker_data (
  user_id uuid primary key references auth.users(id) on delete cascade,
  data jsonb not null default '{"meta":{"title":"Black Friday Tracker 2026","currency":"BRL"},"items":[],"history":[]}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.tracker_data enable row level security;

drop policy if exists "Users can read own tracker_data" on public.tracker_data;
create policy "Users can read own tracker_data"
  on public.tracker_data for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert own tracker_data" on public.tracker_data;
create policy "Users can insert own tracker_data"
  on public.tracker_data for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can update own tracker_data" on public.tracker_data;
create policy "Users can update own tracker_data"
  on public.tracker_data for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
