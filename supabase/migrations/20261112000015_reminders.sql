-- Leafline 11.16 - 15th database update: call reminders.
-- From Find Leads (or a business pop-up) you set a reminder for the business you're calling: when to call back, plus a
-- copy of the company details, the owner's name and your call notes at that moment. Reminders are PRIVATE: each person
-- sees and changes only their own (admins get nothing extra). The app shows today's reminders when you open it and
-- notifies you when one is due.
-- Safe to run more than once. Adds one table and four functions; nothing existing is changed or removed.

create table if not exists public.reminders (
  id         uuid primary key default gen_random_uuid(),
  owner_id   uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  lead_id    text references public.leads(id) on delete set null,
  remind_at  timestamptz not null,
  company    text not null check (length(btrim(company)) between 1 and 120),
  owner_name text not null default '' check (length(owner_name) <= 120),
  phone      text not null default '' check (length(phone) <= 40),
  address    text not null default '' check (length(address) <= 300),
  website    text not null default '' check (length(website) <= 300),
  btype      text not null default '' check (length(btype) <= 80),
  notes      text not null default '' check (length(notes) <= 4000),
  done_at    timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists reminders_owner_at_idx on public.reminders (owner_id, remind_at);
alter table public.reminders enable row level security;

-- Your own reminders only, and only while your account is active.
drop policy if exists reminders_own on public.reminders;
create policy reminders_own on public.reminders for all to authenticated
  using (owner_id = auth.uid() and public.is_active()) with check (owner_id = auth.uid() and public.is_active());

-- All functions run as the caller (security invoker), so the policy above always applies.
create or replace function public.rem_list() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(to_jsonb(r) - 'owner_id' order by r.remind_at), '[]'::jsonb)
  from public.reminders r
  where r.owner_id = auth.uid() and (r.done_at is null or r.done_at > now() - interval '30 days')
$$;

-- Create (no id) or change (id). Everything about the business is a copy, so it stays readable if the lead changes.
create or replace function public.rem_save(p jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare r public.reminders; at timestamptz; co text := btrim(coalesce(p->>'company', '')); lid text := nullif(p->>'lead_id', '');
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p is null or jsonb_typeof(p) <> 'object' then raise exception 'Nothing to save'; end if;
  if coalesce(p->>'remind_at', '') !~ '^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}' then raise exception 'Pick a date and time for the reminder'; end if;
  begin at := (p->>'remind_at')::timestamptz; exception when others then raise exception 'Pick a date and time for the reminder'; end;
  if at is null then raise exception 'Pick a date and time for the reminder'; end if;
  if co = '' or length(co) > 120 then raise exception 'The business name is missing'; end if;
  if lid is not null and not exists (select 1 from public.leads where id = lid) then lid := null; end if;
  if length(coalesce(p->>'notes', '')) > 4000 then raise exception 'Keep the notes under 4000 characters'; end if;
  if length(coalesce(p->>'owner_name', '')) > 120 or length(coalesce(p->>'phone', '')) > 40 or length(coalesce(p->>'address', '')) > 300
     or length(coalesce(p->>'website', '')) > 300 or length(coalesce(p->>'btype', '')) > 80 then raise exception 'Some of the details are too long'; end if;
  if nullif(p->>'id', '') is null then
    insert into public.reminders (owner_id, lead_id, remind_at, company, owner_name, phone, address, website, btype, notes)
    values (auth.uid(), lid, at, co, btrim(coalesce(p->>'owner_name', '')), btrim(coalesce(p->>'phone', '')), btrim(coalesce(p->>'address', '')),
            btrim(coalesce(p->>'website', '')), btrim(coalesce(p->>'btype', '')), coalesce(p->>'notes', ''))
    returning * into r;
  else
    update public.reminders set remind_at = at, company = co, lead_id = lid, owner_name = btrim(coalesce(p->>'owner_name', '')),
        phone = btrim(coalesce(p->>'phone', '')), address = btrim(coalesce(p->>'address', '')), website = btrim(coalesce(p->>'website', '')),
        btype = btrim(coalesce(p->>'btype', '')), notes = coalesce(p->>'notes', ''), done_at = null, updated_at = now()
    where id = (p->>'id')::uuid and owner_id = auth.uid() returning * into r;
    if not found then raise exception 'That reminder was not found'; end if;
  end if;
  return to_jsonb(r) - 'owner_id';
end $$;

-- Done / not done, or move it to a new time (snooze).
create or replace function public.rem_done(p_id uuid, p_done boolean) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare r public.reminders;
begin
  update public.reminders set done_at = case when coalesce(p_done, true) then now() end, updated_at = now()
  where id = p_id and owner_id = auth.uid() returning * into r;
  if not found then raise exception 'That reminder was not found'; end if;
  return to_jsonb(r) - 'owner_id';
end $$;

create or replace function public.rem_snooze(p_id uuid, p_at timestamptz) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare r public.reminders;
begin
  if p_at is null then raise exception 'Pick a new time'; end if;
  update public.reminders set remind_at = p_at, done_at = null, updated_at = now()
  where id = p_id and owner_id = auth.uid() returning * into r;
  if not found then raise exception 'That reminder was not found'; end if;
  return to_jsonb(r) - 'owner_id';
end $$;

create or replace function public.rem_delete(p_id uuid) returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
  delete from public.reminders where id = p_id and owner_id = auth.uid();
  if not found then raise exception 'That reminder was already removed'; end if;
  return jsonb_build_object('ok', true);
end $$;

do $$
declare f text;
begin
  foreach f in array array['public.rem_list()', 'public.rem_save(jsonb)', 'public.rem_done(uuid, boolean)', 'public.rem_snooze(uuid, timestamptz)', 'public.rem_delete(uuid)'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated', f);
  end loop;
end $$;
