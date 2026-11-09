-- Leafline 11.11 - 12th database update: finding new leads from a phone (the website).
-- 1. Google Places: an admin saves the team's Google Places API key and a monthly limit. Every request to Google is
--    counted here first; when the month's limit is reached the database refuses, so the team can stay in Google's
--    free allowance (1,000 a month) no matter how many phones search.
-- 2. "Your PC runs it": when no key is set (or the limit is used up), a phone hands the search to the same person's
--    Leafline app on their PC, which runs the normal Google Maps search and uploads what it finds.
-- 3. Saving found businesses: one function adds them to the shared leads, skipping duplicates by phone number and
--    leaving out businesses someone already called (the same rules as the PC search).
-- Safe to run more than once. Adds three tables and nine functions; nothing existing is changed or removed.

-- ---------------------------------------------------------------- settings (one row) and the monthly counter
create table if not exists public.lead_settings (
  id         boolean primary key default true check (id),
  places_key text check (places_key is null or places_key ~ '^[A-Za-z0-9_-]{20,100}$'),
  month_cap  integer not null default 900 check (month_cap between 0 and 100000),
  updated_by uuid references public.profiles(id) on delete set null,
  updated_at timestamptz not null default now()
);
alter table public.lead_settings enable row level security;   -- no policies: only the functions below read or change it

create table if not exists public.lead_usage (
  month date primary key,                 -- first day of the month (America/Toronto)
  calls integer not null default 0 check (calls >= 0)
);
alter table public.lead_usage enable row level security;      -- no policies: only the functions below

create or replace function public.lead_month() returns date
language sql stable set search_path = '' as $$
  select date_trunc('month', (now() at time zone 'America/Toronto'))::date
$$;

-- everyone active: is phone search set up, how much of this month is used. The key itself is included because the
-- phone sends it to Google directly; the admin restricts it to the website's address in Google Cloud.
create or replace function public.lead_cfg() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare s public.lead_settings; used integer;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select * into s from public.lead_settings where id;
  select calls into used from public.lead_usage where month = public.lead_month();
  return jsonb_build_object('key', coalesce(s.places_key, ''), 'cap', coalesce(s.month_cap, 900), 'used', coalesce(used, 0),
                            'month', public.lead_month(), 'admin', public.is_admin());
end $$;

-- admins only. p_key: null keeps the saved key, '' removes it.
create or replace function public.lead_cfg_set(p_key text, p_cap integer) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k text := btrim(coalesce(p_key, ''));
begin
  if auth.uid() is null or not public.is_active() or not public.is_admin() then raise exception 'Only an administrator can change phone search settings'; end if;
  if p_key is not null and k <> '' and k !~ '^[A-Za-z0-9_-]{20,100}$' then raise exception 'That does not look like a Google API key'; end if;
  if p_cap is null or p_cap < 0 or p_cap > 100000 then raise exception 'The monthly limit must be between 0 and 100000'; end if;
  insert into public.lead_settings (id, places_key, month_cap, updated_by, updated_at)
  values (true, nullif(k, ''), p_cap, auth.uid(), now())
  on conflict (id) do update set
    places_key = case when p_key is null then public.lead_settings.places_key else nullif(k, '') end,
    month_cap = excluded.month_cap, updated_by = excluded.updated_by, updated_at = now();
  return public.lead_cfg();
end $$;

-- called just before each request to Google. Counts it, or refuses when the month's limit is reached.
create or replace function public.lead_quota_take() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare cap integer; used integer; m date := public.lead_month();
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select month_cap into cap from public.lead_settings where id;
  cap := coalesce(cap, 900);
  insert into public.lead_usage (month, calls) values (m, 0) on conflict (month) do nothing;
  update public.lead_usage set calls = calls + 1 where month = m and calls + 1 <= cap returning calls into used;
  if not found then raise exception 'This month''s limit of % Google searches is used up', cap; end if;
  return jsonb_build_object('used', used, 'cap', cap);
end $$;

-- ---------------------------------------------------------------- saving businesses a phone found
-- p_rows: [{id, name, phone, address, website, rating, reviews, hours}], at most 100.
-- New phone number -> added. Same business not called yet -> moved into this search. Already called -> left out.
create or replace function public.lead_add_found(p_search text, p_btype text, p_rows jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r jsonb; pk text; ex record; ids text[] := '{}'; added integer := 0; moved integer := 0; skipped integer := 0;
  v_id text; v_name text; v_phone text; v_hours text;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p_search is null or length(btrim(p_search)) not between 1 and 300 then raise exception 'Missing search'; end if;
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) > 100 then raise exception 'Send 0 to 100 businesses'; end if;
  for r in select * from jsonb_array_elements(p_rows) loop
    v_id := btrim(coalesce(r->>'id', '')); v_name := btrim(coalesce(r->>'name', '')); v_phone := btrim(coalesce(r->>'phone', ''));
    v_hours := coalesce(r->>'hours', '');
    pk := right(regexp_replace(v_phone, '\D', '', 'g'), 10);
    if length(v_id) not between 1 and 300 or length(v_name) not between 1 and 200 or length(pk) < 7 or length(v_phone) > 40 then
      skipped := skipped + 1; continue;
    end if;
    if length(v_hours) > 2000 then v_hours := ''; end if;
    select id, status into ex from public.leads where id = v_id
      union all select id, status from public.leads where phone_key = pk and pk <> '' and id <> v_id
      limit 1;
    if found then
      if ex.status <> 'none' or ex.id = any(ids) then skipped := skipped + 1; continue; end if;   -- called, or already in this batch
      update public.leads set search = btrim(p_search), btype = left(coalesce(p_btype, ''), 80),
        rating = coalesce(nullif(left(r->>'rating', 10), ''), rating), reviews = coalesce(nullif(left(r->>'reviews', 12), ''), reviews),
        hours = case when v_hours <> '' then v_hours else hours end, updated_by = auth.uid()
      where id = ex.id;
      moved := moved + 1; ids := ids || ex.id;
    else
      insert into public.leads (id, name, phone, website, address, rating, reviews, hours, search, btype, added_at, added_by, source, updated_by)
      values (v_id, v_name, v_phone, coalesce(nullif(left(r->>'website', 500), ''), 'N/A'), coalesce(nullif(left(r->>'address', 300), ''), 'N/A'),
              coalesce(nullif(left(r->>'rating', 10), ''), 'N/A'), coalesce(nullif(left(r->>'reviews', 12), ''), 'N/A'), v_hours,
              btrim(p_search), left(coalesce(p_btype, ''), 80), now(), auth.uid(), 'google_places', auth.uid())
      on conflict do nothing;
      if found then added := added + 1; ids := ids || v_id; else skipped := skipped + 1; end if;
    end if;
  end loop;
  return jsonb_build_object('added', added, 'moved', moved, 'skipped', skipped,
    'rows', coalesce((select jsonb_agg(to_jsonb(l)) from public.leads l where l.id = any(ids)), '[]'::jsonb));
end $$;

-- ---------------------------------------------------------------- "your PC runs it"
create table if not exists public.lead_requests (
  id         uuid primary key default gen_random_uuid(),
  owner_id   uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  country    text not null default '' check (length(country) <= 80),
  state      text not null default '' check (length(state) <= 80),
  city       text not null default '' check (length(city) <= 80),
  btype      text not null check (length(btrim(btype)) between 1 and 80),
  q          text not null default '',
  status     text not null default 'pending' check (status in ('pending','running','done','failed','cancelled')),
  found      integer not null default 0 check (found >= 0),
  skipped    integer not null default 0 check (skipped >= 0),
  message    text not null default '' check (length(message) <= 300),
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  updated_at timestamptz not null default now()
);
create index if not exists lead_requests_owner_idx on public.lead_requests (owner_id, status, created_at);
alter table public.lead_requests enable row level security;
drop policy if exists lead_requests_read on public.lead_requests;
create policy lead_requests_read on public.lead_requests for select to authenticated using (owner_id = auth.uid() and public.is_active());
-- no write policies: only the functions below

create or replace function public.lead_req_json(r public.lead_requests) returns jsonb
language sql stable set search_path = '' as $$
  select jsonb_build_object('id', r.id, 'country', r.country, 'state', r.state, 'city', r.city, 'btype', r.btype, 'q', r.q,
    'status', r.status, 'found', r.found, 'skipped', r.skipped, 'message', r.message, 'created_at', r.created_at,
    'claimed_at', r.claimed_at, 'age_s', extract(epoch from now() - r.created_at)::integer)
$$;

-- a request nobody picked up within 30 minutes, or that stopped reporting for 15, is closed
create or replace function public.lead_req_expire() returns void
language sql security definer set search_path = '' as $$
  update public.lead_requests set status = 'failed', updated_at = now(),
    message = case when status = 'pending' then 'Your PC didn''t pick it up within 30 minutes. Open Leafline on your PC and try again.'
                   else 'Your PC stopped answering during the search.' end
  where owner_id = auth.uid() and ((status = 'pending' and created_at < now() - interval '30 minutes')
                                or (status = 'running' and updated_at < now() - interval '15 minutes'))
$$;

create or replace function public.lead_req_add(p_country text, p_state text, p_city text, p_btype text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.lead_requests; c text := btrim(coalesce(p_country, '')); s text := btrim(coalesce(p_state, ''));
  ci text := btrim(coalesce(p_city, '')); b text := btrim(coalesce(p_btype, ''));
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if length(b) not between 1 and 80 then raise exception 'Enter a business type'; end if;
  if c || s || ci = '' then raise exception 'Enter at least a country, state/province or city'; end if;
  if length(c) > 80 or length(s) > 80 or length(ci) > 80 then raise exception 'Keep each place name under 80 characters'; end if;
  perform public.lead_req_expire();
  if (select count(*) from public.lead_requests where owner_id = auth.uid() and status in ('pending','running')) >= 3 then
    raise exception 'You already have 3 searches waiting for your PC. Stop one first.';
  end if;
  insert into public.lead_requests (owner_id, country, state, city, btype) values (auth.uid(), c, s, ci, b) returning * into r;
  return public.lead_req_json(r);
end $$;

create or replace function public.lead_req_get(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.lead_requests;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  perform public.lead_req_expire();
  select * into r from public.lead_requests where id = p_id and owner_id = auth.uid();
  if not found then raise exception 'That search was not found'; end if;
  return public.lead_req_json(r);
end $$;

create or replace function public.lead_req_cancel(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  update public.lead_requests set status = 'cancelled', message = 'Stopped from your phone.', updated_at = now()
  where id = p_id and owner_id = auth.uid() and status in ('pending','running');
  return jsonb_build_object('ok', found);
end $$;

-- the PC app: take the oldest waiting search of the signed-in person (never anyone else's)
create or replace function public.lead_req_claim() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.lead_requests;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  perform public.lead_req_expire();
  select * into r from public.lead_requests where owner_id = auth.uid() and status = 'pending'
    order by created_at limit 1 for update skip locked;
  if not found then return null; end if;
  update public.lead_requests set status = 'running', claimed_at = now(), updated_at = now(), message = 'Your PC is starting the search...'
  where id = r.id returning * into r;
  return public.lead_req_json(r);
end $$;

-- the PC app: progress and the result. Says so if the phone stopped the search meanwhile.
create or replace function public.lead_req_update(p_id uuid, p_status text, p_found integer, p_skipped integer, p_text text, p_q text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare cur text;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p_status not in ('running','done','failed') then raise exception 'Bad status'; end if;
  select status into cur from public.lead_requests where id = p_id and owner_id = auth.uid() for update;
  if not found then raise exception 'That search was not found'; end if;
  if cur <> 'running' then return jsonb_build_object('ok', false, 'cancelled', cur = 'cancelled', 'status', cur); end if;
  update public.lead_requests set status = p_status, found = greatest(coalesce(p_found, 0), 0), skipped = greatest(coalesce(p_skipped, 0), 0),
    message = left(coalesce(p_text, ''), 300), q = left(coalesce(p_q, q), 300), updated_at = now()
  where id = p_id;
  return jsonb_build_object('ok', true, 'cancelled', false, 'status', p_status);
end $$;

revoke all on function public.lead_month() from public, anon;
revoke all on function public.lead_cfg() from public, anon;
revoke all on function public.lead_cfg_set(text, integer) from public, anon;
revoke all on function public.lead_quota_take() from public, anon;
revoke all on function public.lead_add_found(text, text, jsonb) from public, anon;
revoke all on function public.lead_req_json(public.lead_requests) from public, anon;
revoke all on function public.lead_req_expire() from public, anon, authenticated;
revoke all on function public.lead_req_add(text, text, text, text) from public, anon;
revoke all on function public.lead_req_get(uuid) from public, anon;
revoke all on function public.lead_req_cancel(uuid) from public, anon;
revoke all on function public.lead_req_claim() from public, anon;
revoke all on function public.lead_req_update(uuid, text, integer, integer, text, text) from public, anon;
grant execute on function public.lead_cfg() to authenticated;
grant execute on function public.lead_cfg_set(text, integer) to authenticated;
grant execute on function public.lead_quota_take() to authenticated;
grant execute on function public.lead_add_found(text, text, jsonb) to authenticated;
grant execute on function public.lead_req_add(text, text, text, text) to authenticated;
grant execute on function public.lead_req_get(uuid) to authenticated;
grant execute on function public.lead_req_cancel(uuid) to authenticated;
grant execute on function public.lead_req_claim() to authenticated;
grant execute on function public.lead_req_update(uuid, text, integer, integer, text, text) to authenticated;
