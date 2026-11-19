-- Leafline 12.0 - 19th database update: clients.
-- One place for every business you work for: who they are, how to reach them, who on the team looks after them, their
-- status, tags and priority, and a timeline of notes and changes.
--
-- What it does NOT do is copy money. A client's services ARE its deals (price, upfront, monthly, months), its payment
-- history IS those deals' confirmed payments, and its invoices are the invoices that point at those deals (or its lead).
-- client_deals only says which deals belong to which client, so a payment confirmed anywhere in the app shows up on the
-- client straight away and nothing can drift apart.
--
-- Everyone on the team (active accounts) can see and edit clients, the same as deals today. Only admins can delete a
-- client, the same as deals; deleting a client never deletes its deals or invoices, they are only unlinked.
-- All writes go through the functions below, which check the caller and the values. team_health() is replaced so it
-- also reports this update.
-- Safe to run more than once. Adds three tables and some functions; nothing existing is changed or removed.

create table if not exists public.clients (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (length(btrim(name)) between 1 and 120),
  company     text not null default '' check (length(company) <= 120),
  contact     text not null default '' check (length(contact) <= 120),
  phone       text not null default '' check (length(phone) <= 40),
  email       text not null default '' check (length(email) <= 160),
  address     text not null default '' check (length(address) <= 300),
  website     text not null default '' check (length(website) <= 300),
  status      text not null default 'active' check (status in ('active', 'pending', 'inactive', 'completed')),
  priority    text not null default 'normal' check (priority in ('low', 'normal', 'high')),
  tags        text[] not null default '{}' check (cardinality(tags) <= 12),
  team        jsonb not null default '[]' check (jsonb_typeof(team) = 'array' and jsonb_array_length(team) <= 8),
  notes       text not null default '' check (length(notes) <= 4000),
  start_date  date,
  next_date   date,
  next_label  text not null default '' check (length(next_label) <= 80),
  lead_id     text references public.leads(id) on delete set null,
  archived_at timestamptz,
  created_by  uuid references public.profiles(id) on delete set null default auth.uid(),
  created_at  timestamptz not null default now(),
  updated_by  uuid references public.profiles(id) on delete set null,
  updated_at  timestamptz not null default now()
);
create index if not exists clients_name_idx on public.clients (lower(name));

-- which deals (services) belong to which client; a deal belongs to at most one client
create table if not exists public.client_deals (
  deal_id    uuid primary key references public.deals(id) on delete cascade,
  client_id  uuid not null references public.clients(id) on delete cascade,
  linked_by  uuid references public.profiles(id) on delete set null default auth.uid(),
  linked_at  timestamptz not null default now()
);
create index if not exists client_deals_client_idx on public.client_deals (client_id);

-- the client's timeline: notes, calls, meetings, updates, and changes the app writes itself
create table if not exists public.client_events (
  id         uuid primary key default gen_random_uuid(),
  client_id  uuid not null references public.clients(id) on delete cascade,
  kind       text not null check (kind in ('note', 'call', 'meeting', 'update', 'change')),
  body       text not null check (length(btrim(body)) between 1 and 4000),
  created_by uuid references public.profiles(id) on delete set null default auth.uid(),
  created_at timestamptz not null default now()
);
create index if not exists client_events_client_idx on public.client_events (client_id, created_at desc);

alter table public.clients enable row level security;
alter table public.client_deals enable row level security;
alter table public.client_events enable row level security;
drop policy if exists clients_read on public.clients;
create policy clients_read on public.clients for select to authenticated using (public.is_active());
drop policy if exists client_deals_read on public.client_deals;
create policy client_deals_read on public.client_deals for select to authenticated using (public.is_active());
drop policy if exists client_events_read on public.client_events;
create policy client_events_read on public.client_events for select to authenticated using (public.is_active());
-- no insert/update/delete policies: writes only through the functions below

-- ---------------------------------------------------------------- helpers
create or replace function public.cli_json(c public.clients) returns jsonb
language sql stable security definer set search_path = '' as $$
  select to_jsonb(c) || jsonb_build_object(
    'deal_ids', coalesce((select jsonb_agg(cd.deal_id order by cd.linked_at) from public.client_deals cd where cd.client_id = c.id), '[]'::jsonb),
    'events', (select count(*) from public.client_events e where e.client_id = c.id),
    'last_event_at', (select max(e.created_at) from public.client_events e where e.client_id = c.id),
    'created_name', (select p.display_name from public.profiles p where p.id = c.created_by))
$$;

create or replace function public.cli_log(p_client uuid, p_kind text, p_body text) returns void
language sql security definer set search_path = '' as $$
  insert into public.client_events (client_id, kind, body, created_by) values (p_client, p_kind, left(p_body, 4000), auth.uid())
$$;

create or replace function public.cli_check() returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
end $$;

-- ---------------------------------------------------------------- reading
create or replace function public.cli_list() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform public.cli_check();
  return jsonb_build_object('admin', public.is_admin(),
    'clients', coalesce((select jsonb_agg(public.cli_json(c) order by c.archived_at nulls first, lower(c.name)) from public.clients c), '[]'::jsonb));
end $$;

create or replace function public.cli_get(p_id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare c public.clients;
begin
  perform public.cli_check();
  select * into c from public.clients where id = p_id;
  if not found then raise exception 'That client was not found'; end if;
  return public.cli_json(c) || jsonb_build_object('timeline', coalesce((
    select jsonb_agg(jsonb_build_object('id', e.id, 'kind', e.kind, 'body', e.body, 'created_at', e.created_at, 'created_by', e.created_by,
                                        'created_name', p.display_name) order by e.created_at desc)
    from (select * from public.client_events where client_id = p_id order by created_at desc limit 300) e
    left join public.profiles p on p.id = e.created_by), '[]'::jsonb));
end $$;

-- ---------------------------------------------------------------- saving
-- Create (no id) or change (id). Returns the saved client.
create or replace function public.cli_save(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); c public.clients; old public.clients; nm text := btrim(coalesce(p->>'name', ''));
        st text := coalesce(nullif(p->>'status', ''), 'active'); pr text := coalesce(nullif(p->>'priority', ''), 'normal');
        tg text[] := '{}'; tm jsonb := '[]'::jsonb; t jsonb; tid uuid; lid text := nullif(p->>'lead_id', '');
        sd date; nd date; em text := btrim(coalesce(p->>'email', ''));
begin
  perform public.cli_check();
  if p is null or jsonb_typeof(p) <> 'object' then raise exception 'Nothing to save'; end if;
  if nm = '' then raise exception 'Type the client''s name'; end if;
  if length(nm) > 120 then raise exception 'Keep the name under 120 characters'; end if;
  if st not in ('active', 'pending', 'inactive', 'completed') then raise exception 'Pick a status'; end if;
  if pr not in ('low', 'normal', 'high') then raise exception 'Pick a priority'; end if;
  if em <> '' and em !~ '^[^\s@]+@[^\s@]+\.[^\s@]{2,}$' then raise exception 'That email doesn''t look right'; end if;
  if length(coalesce(p->>'company', '')) > 120 or length(coalesce(p->>'contact', '')) > 120 or length(coalesce(p->>'phone', '')) > 40
     or length(em) > 160 or length(coalesce(p->>'address', '')) > 300 or length(coalesce(p->>'website', '')) > 300
     or length(coalesce(p->>'next_label', '')) > 80 then raise exception 'Some of the details are too long'; end if;
  if length(coalesce(p->>'notes', '')) > 4000 then raise exception 'Keep the notes under 4000 characters'; end if;
  if jsonb_typeof(p->'tags') = 'array' then
    select coalesce(array_agg(distinct x), '{}') into tg from (
      select left(btrim(v), 30) x from jsonb_array_elements_text(p->'tags') v where btrim(v) <> '') s;
    if cardinality(tg) > 12 then raise exception 'Up to 12 tags'; end if;
  end if;
  if jsonb_typeof(p->'team') = 'array' then
    for t in select * from jsonb_array_elements(p->'team') loop
      begin tid := (t->>'id')::uuid; exception when others then raise exception 'Pick teammates from the list'; end;
      if not exists (select 1 from public.profiles where id = tid) then raise exception 'Pick teammates from the list'; end if;
      if tm @> jsonb_build_array(jsonb_build_object('id', tid)) then continue; end if;
      tm := tm || jsonb_build_array(jsonb_build_object('id', tid, 'role', left(btrim(coalesce(t->>'role', '')), 80)));
    end loop;
    if jsonb_array_length(tm) > 8 then raise exception 'Up to 8 teammates'; end if;
  end if;
  begin sd := nullif(p->>'start_date', '')::date; nd := nullif(p->>'next_date', '')::date;
  exception when others then raise exception 'One of the dates doesn''t look right'; end;
  if lid is not null and not exists (select 1 from public.leads where id = lid) then lid := null; end if;

  if nullif(p->>'id', '') is null then
    insert into public.clients (name, company, contact, phone, email, address, website, status, priority, tags, team, notes,
                                start_date, next_date, next_label, lead_id, created_by, updated_by)
    values (nm, btrim(coalesce(p->>'company', '')), btrim(coalesce(p->>'contact', '')), btrim(coalesce(p->>'phone', '')), em,
            btrim(coalesce(p->>'address', '')), btrim(coalesce(p->>'website', '')), st, pr, tg, tm, coalesce(p->>'notes', ''),
            coalesce(sd, current_date), nd, btrim(coalesce(p->>'next_label', '')), lid, me, me)
    returning * into c;
    perform public.cli_log(c.id, 'change', 'Client added');
  else
    select * into old from public.clients where id = (p->>'id')::uuid for update;
    if not found then raise exception 'That client was not found'; end if;
    update public.clients set name = nm, company = btrim(coalesce(p->>'company', '')), contact = btrim(coalesce(p->>'contact', '')),
        phone = btrim(coalesce(p->>'phone', '')), email = em, address = btrim(coalesce(p->>'address', '')),
        website = btrim(coalesce(p->>'website', '')), status = st, priority = pr, tags = tg, team = tm, notes = coalesce(p->>'notes', ''),
        start_date = sd, next_date = nd, next_label = btrim(coalesce(p->>'next_label', '')), lead_id = lid,
        updated_by = me, updated_at = now()
    where id = old.id returning * into c;
    if old.status is distinct from c.status then perform public.cli_log(c.id, 'change', 'Status: ' || old.status || ' → ' || c.status); end if;
    if old.priority is distinct from c.priority then perform public.cli_log(c.id, 'change', 'Priority: ' || old.priority || ' → ' || c.priority); end if;
    if old.team is distinct from c.team then perform public.cli_log(c.id, 'change', 'Team changed'); end if;
  end if;
  return public.cli_json(c);
end $$;

create or replace function public.cli_archive(p_id uuid, p_on boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare c public.clients;
begin
  perform public.cli_check();
  update public.clients set archived_at = case when coalesce(p_on, true) then coalesce(archived_at, now()) end,
         updated_by = auth.uid(), updated_at = now()
  where id = p_id returning * into c;
  if not found then raise exception 'That client was not found'; end if;
  perform public.cli_log(c.id, 'change', case when coalesce(p_on, true) then 'Archived' else 'Reactivated' end);
  return public.cli_json(c);
end $$;

-- Admins only. The client, its timeline and its links go; its deals and invoices stay (they are only unlinked).
create or replace function public.cli_delete(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform public.cli_check();
  if not public.is_admin() then raise exception 'Only an admin can delete a client. You can archive it instead.'; end if;
  delete from public.clients where id = p_id;
  if not found then raise exception 'That client was already removed'; end if;
  return jsonb_build_object('ok', true);
end $$;

-- Add a deal (service) to a client, or take it off (p_on false). Moving a deal from another client is allowed and logged.
create or replace function public.cli_link(p_client uuid, p_deal uuid, p_on boolean default true) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare d public.deals; prev uuid; c public.clients;
begin
  perform public.cli_check();
  select * into c from public.clients where id = p_client;
  if not found then raise exception 'That client was not found'; end if;
  select * into d from public.deals where id = p_deal;
  if not found then raise exception 'That deal was not found. If you just added it, wait for it to sync and try again.'; end if;
  select client_id into prev from public.client_deals where deal_id = p_deal;
  if coalesce(p_on, true) then
    if prev = p_client then return public.cli_json(c); end if;
    insert into public.client_deals (deal_id, client_id, linked_by) values (p_deal, p_client, auth.uid())
    on conflict (deal_id) do update set client_id = excluded.client_id, linked_by = excluded.linked_by, linked_at = now();
    perform public.cli_log(p_client, 'change', 'Service added: ' || d.client);
    if prev is not null then perform public.cli_log(prev, 'change', 'Service moved to ' || c.name || ': ' || d.client); end if;
  else
    delete from public.client_deals where deal_id = p_deal and client_id = p_client;
    if found then perform public.cli_log(p_client, 'change', 'Service removed: ' || d.client); end if;
  end if;
  update public.clients set updated_at = now(), updated_by = auth.uid() where id = p_client returning * into c;
  return public.cli_json(c);
end $$;

-- A note, call, meeting or update on the client's timeline.
create or replace function public.cli_note(p_client uuid, p_kind text, p_body text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare e public.client_events;
begin
  perform public.cli_check();
  if coalesce(p_kind, '') not in ('note', 'call', 'meeting', 'update') then raise exception 'Pick what kind of entry this is'; end if;
  if length(btrim(coalesce(p_body, ''))) = 0 then raise exception 'Write something first'; end if;
  if length(p_body) > 4000 then raise exception 'Keep it under 4000 characters'; end if;
  if not exists (select 1 from public.clients where id = p_client) then raise exception 'That client was not found'; end if;
  insert into public.client_events (client_id, kind, body, created_by) values (p_client, p_kind, btrim(p_body), auth.uid()) returning * into e;
  update public.clients set updated_at = now() where id = p_client;
  return to_jsonb(e);
end $$;

-- Your own timeline entries, or any if you're an admin. Entries the app wrote itself ('change') stay.
create or replace function public.cli_note_delete(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform public.cli_check();
  delete from public.client_events where id = p_id and kind <> 'change' and (created_by = auth.uid() or public.is_admin());
  if not found then raise exception 'You can only remove your own notes'; end if;
  return jsonb_build_object('ok', true);
end $$;

do $$
declare f text;
begin
  foreach f in array array['public.cli_json(public.clients)', 'public.cli_log(uuid, text, text)', 'public.cli_check()'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
  end loop;
  foreach f in array array['public.cli_list()', 'public.cli_get(uuid)', 'public.cli_save(jsonb)', 'public.cli_archive(uuid, boolean)',
                           'public.cli_delete(uuid)', 'public.cli_link(uuid, uuid, boolean)', 'public.cli_note(uuid, text, text)',
                           'public.cli_note_delete(uuid)'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated', f);
  end loop;
end $$;

-- ---------------------------------------------------------------- health check reports update 19
create or replace function public.team_health() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u jsonb; banner boolean;
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Administrators only'; end if;
  begin
    execute 'select exists (select 1 from storage.buckets where id = ''media'' and file_size_limit >= 104857600)' into banner;
  exception when others then banner := null;   -- can't tell from here
  end;
  u := jsonb_build_object(
    '2',  exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'events' and column_name = 'done'),
    '3',  exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'profiles' and column_name = 'avatar'),
    '4',  exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'profiles' and column_name = 'title'),
    '5',  to_regclass('public.posts') is not null,
    '6',  exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'call_log' and column_name = 'credited_to'),
    '7',  exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'deals' and column_name = 'confirmed'),
    '8',  to_regclass('public.conversations') is not null,
    '9',  to_regclass('public.user_settings') is not null,
    '10', banner,
    '11', to_regclass('public.expenses') is not null,
    '12', to_regclass('public.lead_settings') is not null,
    '13', to_regclass('public.meeting_checks') is not null,
    '14', to_regclass('public.invoices') is not null,
    '15', to_regclass('public.reminders') is not null,
    '16', to_regclass('public.deal_splits') is not null,
    '17', to_regclass('public.lead_stages') is not null,
    '18', to_regclass('public.email_drafts') is not null,
    '19', true);
  return jsonb_build_object('updates', u, 'checked_at', now(), 'people', coalesce((
    select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'username', p.username, 'role', p.role, 'active', p.active,
                                        'last_seen', p.last_seen, 'version', s.version, 'platform', s.platform, 'sync_state', s.sync_state,
                                        'pending', s.pending, 'last_error', s.last_error, 'reported_at', s.updated_at)
                     order by p.active desc, p.display_name)
    from public.profiles p left join public.app_status s on s.user_id = p.id), '[]'::jsonb));
end $$;
revoke all on function public.team_health() from public;
grant execute on function public.team_health() to authenticated;
