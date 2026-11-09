-- Leafline 11.13 - 13th database update: confirming that meetings happened.
-- A meeting is a lead marked "Meeting set up" with a meeting date and time. Once that time has passed, someone confirms
-- it took place. A confirmation belongs to one meeting time: if the meeting is moved, the new time needs confirming.
-- Times are stored exactly as the app shows them ("YYYY-MM-DD HH:MM", Toronto time), the same on every device.
-- Safe to run more than once. Adds one table and three functions; nothing existing is changed or removed.

create table if not exists public.meeting_checks (
  lead_id      text not null references public.leads(id) on delete cascade,
  meeting_key  text not null check (meeting_key ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$'),
  confirmed_by uuid references public.profiles(id) on delete set null default auth.uid(),
  confirmed_at timestamptz not null default now(),
  primary key (lead_id, meeting_key)
);
alter table public.meeting_checks enable row level security;
drop policy if exists meeting_checks_read on public.meeting_checks;
create policy meeting_checks_read on public.meeting_checks for select to authenticated using (public.is_active());
-- no write policies: changes only go through the functions below

drop trigger if exists audit_meeting_checks on public.meeting_checks;
create trigger audit_meeting_checks after insert or update or delete on public.meeting_checks for each row execute function public.audit_row();

-- confirmations for meetings since p_since (a 'YYYY-MM-DD' day; null = all)
create or replace function public.mtg_list(p_since text) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('lead_id', m.lead_id, 'meeting_key', m.meeting_key, 'confirmed_by', m.confirmed_by,
           'confirmed_name', p.display_name, 'confirmed_at', m.confirmed_at) order by m.meeting_key), '[]'::jsonb)
  from public.meeting_checks m left join public.profiles p on p.id = m.confirmed_by
  where p_since is null or m.meeting_key >= p_since
$$;

-- any active teammate can confirm a meeting that has already started
create or replace function public.mtg_confirm(p_lead text, p_key text) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p_key is null or p_key !~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$' then raise exception 'That meeting time is not valid'; end if;
  if not exists (select 1 from public.leads where id = p_lead) then raise exception 'That business was not found'; end if;
  if p_key > to_char(now() at time zone 'America/Toronto', 'YYYY-MM-DD HH24:MI') then raise exception 'This meeting hasn''t happened yet'; end if;
  insert into public.meeting_checks (lead_id, meeting_key, confirmed_by) values (p_lead, p_key, auth.uid())
  on conflict (lead_id, meeting_key) do nothing;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.mtg_unconfirm(p_lead text, p_key text) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  delete from public.meeting_checks where lead_id = p_lead and meeting_key = p_key;
  return jsonb_build_object('ok', found);
end $$;

revoke all on function public.mtg_list(text) from public, anon;
revoke all on function public.mtg_confirm(text, text) from public, anon;
revoke all on function public.mtg_unconfirm(text, text) from public, anon;
grant execute on function public.mtg_list(text) to authenticated;
grant execute on function public.mtg_confirm(text, text) to authenticated;
grant execute on function public.mtg_unconfirm(text, text) to authenticated;
