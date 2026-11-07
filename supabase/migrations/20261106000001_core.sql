-- Leafline shared database: core schema, row level security, audit trail, realtime.
-- Run once in Supabase: Dashboard > SQL Editor > paste > Run. Safe to re-run (idempotent where practical).

-- ---------------------------------------------------------------- helpers
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null unique check (username ~ '^[a-z0-9_.-]{2,32}$'),
  display_name text not null,
  role text not null default 'employee' check (role in ('admin','employee')),
  active boolean not null default true,
  must_change_password boolean not null default true,
  status_text text not null default 'Offline',
  last_seen timestamptz,
  created_at timestamptz not null default now()
);

create or replace function public.is_active() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles p where p.id = auth.uid() and p.active)
$$;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles p where p.id = auth.uid() and p.active and p.role = 'admin')
$$;

-- Bumps version/updated_at on every update. Clients send "PATCH ... ?id=eq.X&version=eq.N":
-- zero rows back means someone else saved first (conflict) and the client must re-read.
create or replace function public.touch_row() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.version := old.version + 1;
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end $$;

-- ---------------------------------------------------------------- tables
create table if not exists public.leads (
  id text primary key,                       -- same id the desktop app already uses (Google place id)
  name text not null,
  phone text not null default '',
  phone_key text generated always as (right(regexp_replace(phone, '\D', '', 'g'), 10)) stored,
  owner_name text not null default 'N/A',
  email text not null default 'N/A',
  rating text not null default 'N/A',
  reviews text not null default 'N/A',
  website text not null default 'N/A',
  address text not null default 'N/A',
  search text,
  btype text not null default '',
  hours text not null default '',
  status text not null default 'none' check (status in ('none','green','yellow','orange','red')),
  notes text not null default '',
  enriched boolean not null default false,
  added_at timestamptz,
  called_at timestamptz,
  meeting_at timestamptz,
  added_by uuid references public.profiles(id),
  called_by uuid references public.profiles(id),   -- NULL = unassigned (e.g. legacy data)
  source text not null default 'app',
  raw jsonb,                                       -- original legacy row, untouched
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid
);
-- Duplicate protection: one lead per phone number (last 10 digits).
create unique index if not exists leads_phone_key_uq on public.leads (phone_key) where phone_key <> '';
create index if not exists leads_status_idx on public.leads (status);
create index if not exists leads_updated_idx on public.leads (updated_at);

create table if not exists public.call_log (
  id uuid primary key default gen_random_uuid(),
  client_op_id uuid unique,                        -- retry-safe: the same op can never insert twice
  lead_id text references public.leads(id) on delete set null,
  employee_id uuid references public.profiles(id) default auth.uid(),  -- NULL = unassigned
  phone text not null default '',
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  duration_s integer check (duration_s is null or duration_s >= 0),
  outcome text not null check (outcome in ('no_answer','voicemail','interested','not_interested',
                                           'follow_up','meeting_booked','sale_completed')),
  notes text not null default '',
  source text not null default 'app',           -- app (result marked in Leafline) | legacy_status (derived from old data, not a real call record)
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid
);
create index if not exists call_log_started_idx on public.call_log (started_at);
create index if not exists call_log_emp_idx on public.call_log (employee_id, started_at);

create table if not exists public.deals (
  id uuid primary key default gen_random_uuid(),
  client_op_id uuid unique,
  legacy_key text unique,
  client text not null,
  upfront numeric(12,2) not null default 0 check (upfront >= 0),
  monthly numeric(12,2) not null default 0 check (monthly >= 0),
  months integer not null default 0 check (months >= 0),   -- 0 = never ends
  closed_at date,
  first_bill date,
  notes text not null default '',
  lead_id text references public.leads(id) on delete set null,
  owner_id uuid references public.profiles(id),            -- NULL = unassigned
  source text not null default 'app',
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid,
  created_by uuid default auth.uid()
);

create table if not exists public.events (
  id uuid primary key default gen_random_uuid(),
  client_op_id uuid unique,
  legacy_key text unique,
  title text not null,
  kind text not null default 'event' check (kind in ('event','meeting','follow_up','call')),
  day date not null,
  start_time text not null default '',
  color text not null default '',
  icon text not null default '',
  repeat_kind text not null default 'none' check (repeat_kind in ('none','daily','weekly','monthly','yearly')),
  until date,
  notes text not null default '',
  lead_id text references public.leads(id) on delete set null,
  assigned_to uuid references public.profiles(id),
  created_by uuid references public.profiles(id) default auth.uid(),
  source text not null default 'app',
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid
);
create index if not exists events_day_idx on public.events (day);

create table if not exists public.notes (            -- notes AND call scripts
  id uuid primary key default gen_random_uuid(),
  client_op_id uuid unique,
  kind text not null default 'note' check (kind in ('note','script')),
  scope text not null default 'personal' check (scope in ('personal','shared')),
  owner_id uuid not null references public.profiles(id) default auth.uid(),
  title text not null default 'Untitled',
  folder text not null default '',
  body text not null default '',                      -- plain text for notes, sanitized HTML for scripts
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid
);

create table if not exists public.activity (          -- written only by triggers, so it can't be forged
  id bigint generated always as identity primary key,
  employee_id uuid references public.profiles(id),
  kind text not null,
  summary text not null,
  ref_table text,
  ref_id text,
  created_at timestamptz not null default now()
);
create index if not exists activity_created_idx on public.activity (created_at desc);

create table if not exists public.settings (key text primary key, value jsonb not null, updated_at timestamptz not null default now());
insert into public.settings(key, value) values
  ('daily_targets', '{"calls":100,"connections":20,"meetings":3,"sales":1}'::jsonb)
on conflict (key) do nothing;

create table if not exists public.audit_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  actor uuid,
  table_name text not null,
  row_id text,
  action text not null,
  old_row jsonb,
  new_row jsonb
);
create index if not exists audit_at_idx on public.audit_log (at desc);

create table if not exists public.import_batches (
  id uuid primary key default gen_random_uuid(),
  source_file text not null,
  source_sha256 text not null,
  imported_at timestamptz not null default now(),
  report jsonb not null
);
create table if not exists public.legacy_duplicates (  -- duplicates are preserved here, never deleted
  id uuid primary key default gen_random_uuid(),
  batch_id uuid references public.import_batches(id),
  kept_lead_id text,
  reason text not null,
  original jsonb not null
);

-- ---------------------------------------------------------------- triggers
do $$
declare t text;
begin
  foreach t in array array['leads','call_log','deals','events','notes'] loop
    execute format('drop trigger if exists touch_%1$s on public.%1$s', t);
    execute format('create trigger touch_%1$s before update on public.%1$s for each row execute function public.touch_row()', t);
  end loop;
end $$;

create or replace function public.audit_row() returns trigger
language plpgsql security definer set search_path = '' as $$
declare rid text;
begin
  rid := coalesce((case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end)->>'id', '');
  insert into public.audit_log(actor, table_name, row_id, action, old_row, new_row)
  values (auth.uid(), tg_table_name, rid, tg_op,
          case when tg_op in ('UPDATE','DELETE') then to_jsonb(old) end,
          case when tg_op in ('INSERT','UPDATE') then to_jsonb(new) end);
  return null;
end $$;
-- personal notes are deliberately NOT audited so administrators cannot read private notes.
do $$
declare t text;
begin
  foreach t in array array['leads','call_log','deals','events'] loop
    execute format('drop trigger if exists audit_%1$s on public.%1$s', t);
    execute format('create trigger audit_%1$s after insert or update or delete on public.%1$s for each row execute function public.audit_row()', t);
  end loop;
end $$;

-- Accounts are audited only when something meaningful changes (not on every "last seen" heartbeat).
drop trigger if exists audit_profiles_ins on public.profiles;
drop trigger if exists audit_profiles_del on public.profiles;
drop trigger if exists audit_profiles_upd on public.profiles;
create trigger audit_profiles_ins after insert on public.profiles for each row execute function public.audit_row();
create trigger audit_profiles_del after delete on public.profiles for each row execute function public.audit_row();
create trigger audit_profiles_upd after update on public.profiles for each row
  when (old.role is distinct from new.role or old.active is distinct from new.active
        or old.username is distinct from new.username or old.must_change_password is distinct from new.must_change_password)
  execute function public.audit_row();

create or replace function public.guard_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or public.is_admin() then return new; end if;   -- service role / admin
  if new.id <> old.id or new.username <> old.username or new.role <> old.role or new.active <> old.active then
    raise exception 'Only an administrator can change username, role or active status';
  end if;
  if new.must_change_password and not old.must_change_password then
    raise exception 'Only an administrator can require a password change';
  end if;
  return new;
end $$;
drop trigger if exists guard_profile on public.profiles;
create trigger guard_profile before update on public.profiles for each row execute function public.guard_profile();

create or replace function public.guard_note() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (new.owner_id <> old.owner_id or new.scope <> old.scope) and old.owner_id <> auth.uid() then
    raise exception 'Only the note owner can change its owner or visibility';
  end if;
  return new;
end $$;
drop trigger if exists guard_note on public.notes;
create trigger guard_note before update on public.notes for each row execute function public.guard_note();

-- Activity feed (only when a signed-in employee acts; bulk imports stay silent).
create or replace function public.feed() returns trigger
language plpgsql security definer set search_path = '' as $$
declare who text; msg text; lead_name text;
begin
  if auth.uid() is null then return null; end if;
  select display_name into who from public.profiles where id = auth.uid();
  if tg_table_name = 'call_log' then
    select name into lead_name from public.leads where id = new.lead_id;
    msg := case new.outcome
      when 'meeting_booked' then who || ' booked a meeting' || coalesce(' with ' || lead_name, '')
      when 'sale_completed' then who || ' completed a sale' || coalesce(' with ' || lead_name, '')
      when 'follow_up' then who || ' added a follow-up' || coalesce(' for ' || lead_name, '')
      else who || ' logged a call' || coalesce(' to ' || lead_name, '') || ' (' || replace(new.outcome, '_', ' ') || ')' end;
    insert into public.activity(employee_id, kind, summary, ref_table, ref_id) values (auth.uid(), 'call', msg, 'call_log', new.id::text);
  elsif tg_table_name = 'deals' then
    insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
    values (auth.uid(), 'deal', who || ' closed a deal: ' || new.client, 'deals', new.id::text);
  elsif tg_table_name = 'events' and tg_op = 'INSERT' then
    insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
    values (auth.uid(), 'event', who || ' added "' || new.title || '" to the calendar', 'events', new.id::text);
  elsif tg_table_name = 'leads' and tg_op = 'UPDATE' and new.status is distinct from old.status and new.status <> 'none' then
    insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
    values (auth.uid(), 'lead', who || ' updated ' || new.name || ' (' || new.status || ')', 'leads', new.id);
  end if;
  return null;
end $$;
drop trigger if exists feed_call_log on public.call_log;
create trigger feed_call_log after insert on public.call_log for each row execute function public.feed();
drop trigger if exists feed_deals on public.deals;
create trigger feed_deals after insert on public.deals for each row execute function public.feed();
drop trigger if exists feed_events on public.events;
create trigger feed_events after insert on public.events for each row execute function public.feed();
drop trigger if exists feed_leads on public.leads;
create trigger feed_leads after update on public.leads for each row execute function public.feed();

-- ---------------------------------------------------------------- statistics
-- "Connection" = a person answered (interested, not interested, follow-up, meeting, sale).
-- Day boundaries use America/Toronto.
create or replace function public.daily_stats(p_from date, p_to date)
returns table(day date, employee_id uuid, calls bigint, connections bigint, prospects bigint, meetings bigint, sales bigint)
language sql stable security invoker set search_path = '' as $$
  select (c.started_at at time zone 'America/Toronto')::date, c.employee_id,
         count(*),
         count(*) filter (where c.outcome in ('interested','not_interested','follow_up','meeting_booked','sale_completed')),
         count(distinct c.lead_id),
         count(*) filter (where c.outcome = 'meeting_booked'),
         count(*) filter (where c.outcome = 'sale_completed')
  from public.call_log c
  where c.source <> 'legacy_status'
    and (c.started_at at time zone 'America/Toronto')::date between p_from and p_to
  group by 1, 2
$$;

-- ---------------------------------------------------------------- row level security
alter table public.profiles enable row level security;
alter table public.leads enable row level security;
alter table public.call_log enable row level security;
alter table public.deals enable row level security;
alter table public.events enable row level security;
alter table public.notes enable row level security;
alter table public.activity enable row level security;
alter table public.settings enable row level security;
alter table public.audit_log enable row level security;
alter table public.import_batches enable row level security;
alter table public.legacy_duplicates enable row level security;

do $$
declare r record;
begin   -- reset policies so this file can be re-run
  for r in select schemaname, tablename, policyname from pg_policies where schemaname = 'public' loop
    execute format('drop policy %I on %I.%I', r.policyname, r.schemaname, r.tablename);
  end loop;
end $$;

create policy profiles_read on public.profiles for select to authenticated using (public.is_active());
create policy profiles_update_self on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());
create policy profiles_update_admin on public.profiles for update to authenticated using (public.is_admin()) with check (public.is_admin());
-- no insert/delete policy: accounts are created and removed only through the admin API (service role).

create policy leads_read on public.leads for select to authenticated using (public.is_active());
create policy leads_insert on public.leads for insert to authenticated with check (public.is_active());
create policy leads_update on public.leads for update to authenticated using (public.is_active()) with check (public.is_active());
create policy leads_delete on public.leads for delete to authenticated using (public.is_admin());

create policy calls_read on public.call_log for select to authenticated using (public.is_active());
create policy calls_insert on public.call_log for insert to authenticated with check (public.is_active() and (employee_id = auth.uid() or public.is_admin()));
create policy calls_update on public.call_log for update to authenticated using (public.is_active() and (employee_id = auth.uid() or public.is_admin())) with check (public.is_active() and (employee_id = auth.uid() or public.is_admin()));
create policy calls_delete on public.call_log for delete to authenticated using (public.is_admin());

create policy deals_read on public.deals for select to authenticated using (public.is_active());
create policy deals_insert on public.deals for insert to authenticated with check (public.is_active());
create policy deals_update on public.deals for update to authenticated using (public.is_active()) with check (public.is_active());
create policy deals_delete on public.deals for delete to authenticated using (public.is_admin());

create policy events_read on public.events for select to authenticated using (public.is_active());
create policy events_insert on public.events for insert to authenticated with check (public.is_active());
create policy events_update on public.events for update to authenticated using (public.is_active() and (created_by = auth.uid() or assigned_to = auth.uid() or public.is_admin())) with check (public.is_active());
create policy events_delete on public.events for delete to authenticated using (public.is_active() and (created_by = auth.uid() or public.is_admin()));

-- personal notes: owner only. shared notes: everyone reads and edits, only owner/admin deletes.
create policy notes_read on public.notes for select to authenticated using (public.is_active() and (scope = 'shared' or owner_id = auth.uid()));
create policy notes_insert on public.notes for insert to authenticated with check (public.is_active() and owner_id = auth.uid());
create policy notes_update on public.notes for update to authenticated using (public.is_active() and (owner_id = auth.uid() or scope = 'shared')) with check (public.is_active() and (scope = 'shared' or owner_id = auth.uid()));
create policy notes_delete on public.notes for delete to authenticated using (public.is_active() and (owner_id = auth.uid() or (scope = 'shared' and public.is_admin())));

create policy activity_read on public.activity for select to authenticated using (public.is_active());
create policy settings_read on public.settings for select to authenticated using (public.is_active());
create policy settings_write on public.settings for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy audit_admin on public.audit_log for select to authenticated using (public.is_admin());
create policy batches_admin on public.import_batches for select to authenticated using (public.is_admin());
create policy dups_admin on public.legacy_duplicates for select to authenticated using (public.is_admin());

-- ---------------------------------------------------------------- realtime
do $$
declare t text;
begin
  foreach t in array array['leads','call_log','deals','events','notes','activity','profiles','settings'] loop
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;
