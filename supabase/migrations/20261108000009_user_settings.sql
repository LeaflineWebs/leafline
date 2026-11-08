-- Leafline 11.8 — 9th database update: your own account details follow you to every device.
-- Before this, name/email/phone/company typed in Settings > Account were kept only on the device where they were typed,
-- so the website, the desktop app and a second computer each showed their own copy (it looked like they never saved).
-- It also adds reactions on notes and scripts shared with the whole team (bottom of this file).
-- Safe to run more than once. Adds two tables and four functions; nothing existing is changed or removed.

create table if not exists public.user_settings (
  user_id    uuid primary key references public.profiles(id) on delete cascade,
  data       jsonb not null default '{}'::jsonb
             check (jsonb_typeof(data) = 'object' and length(data::text) <= 4000),
  updated_at timestamptz not null default now()
);
alter table public.user_settings enable row level security;

-- Private: each person reads and writes only their own row. Admins get nothing extra.
drop policy if exists user_settings_own on public.user_settings;
create policy user_settings_own on public.user_settings for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Both functions run as the caller (security invoker), so the policy above always applies.
create or replace function public.me_settings_get() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce((select jsonb_build_object('data', s.data, 'updated_at', s.updated_at)
                   from public.user_settings s where s.user_id = auth.uid()), '{}'::jsonb)
$$;

create or replace function public.me_settings_set(p_data jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare r public.user_settings;
begin
  if auth.uid() is null then raise exception 'Sign in first'; end if;
  if p_data is null or jsonb_typeof(p_data) <> 'object' then raise exception 'Settings must be an object'; end if;
  insert into public.user_settings (user_id, data, updated_at) values (auth.uid(), p_data, now())
  on conflict (user_id) do update set data = public.user_settings.data || excluded.data, updated_at = now()
  returning * into r;
  return jsonb_build_object('data', r.data, 'updated_at', r.updated_at);
end $$;

revoke all on function public.me_settings_get() from public, anon;
revoke all on function public.me_settings_set(jsonb) from public, anon;
grant execute on function public.me_settings_get() to authenticated;
grant execute on function public.me_settings_set(jsonb) to authenticated;

-- ---------------------------------------------------------------- reactions on shared notes and scripts
-- Anyone on the team can react to a note or script shared with the whole team. Private notes can't be reacted to.
create table if not exists public.note_reactions (
  note_id    uuid not null references public.notes(id) on delete cascade,
  user_id    uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  emoji      text not null check (emoji in ('👍','🔥','💡','🎉','❤️','😂')),
  created_at timestamptz not null default now(),
  primary key (note_id, user_id, emoji)
);
alter table public.note_reactions enable row level security;
drop policy if exists note_reactions_read on public.note_reactions;
create policy note_reactions_read on public.note_reactions for select to authenticated
  using (public.is_active() and exists (select 1 from public.notes n where n.id = note_id and n.scope = 'shared'));
-- no insert/update/delete policies: changes only go through note_react(), which checks everything.

create or replace function public.note_react(p_note uuid, p_emoji text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare added boolean;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if not exists (select 1 from public.notes where id = p_note and scope = 'shared') then
    raise exception 'Only notes and scripts shared with the team can have reactions';
  end if;
  if p_emoji is null or p_emoji not in ('👍','🔥','💡','🎉','❤️','😂') then raise exception 'Pick one of the listed reactions'; end if;
  delete from public.note_reactions where note_id = p_note and user_id = auth.uid() and emoji = p_emoji;
  added := not found;
  if added then insert into public.note_reactions (note_id, user_id, emoji) values (p_note, auth.uid(), p_emoji); end if;
  return jsonb_build_object('on', added);
end $$;

create or replace function public.note_reactions_for(p_notes uuid[]) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('note_id', x.note_id, 'emoji', x.emoji, 'n', x.n, 'mine', x.mine, 'who', x.who)), '[]'::jsonb)
  from (select r.note_id, r.emoji, count(*)::int as n, bool_or(r.user_id = auth.uid()) as mine,
               array_agg(p.display_name order by r.created_at) as who
        from public.note_reactions r join public.profiles p on p.id = r.user_id
        where r.note_id = any(p_notes) group by r.note_id, r.emoji) x
$$;

revoke all on function public.note_react(uuid, text) from public, anon;
revoke all on function public.note_reactions_for(uuid[]) from public, anon;
grant execute on function public.note_react(uuid, text) to authenticated;
grant execute on function public.note_reactions_for(uuid[]) to authenticated;

do $$ begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'note_reactions') then
    alter publication supabase_realtime add table public.note_reactions;
  end if;
exception when undefined_object then null;      -- no realtime publication (local test databases)
end $$;
