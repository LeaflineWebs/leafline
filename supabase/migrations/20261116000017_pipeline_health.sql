-- 17th update (Leafline 11.19): pipeline, duplicate / do-not-call warnings, and the admin health page.
-- Safe to run more than once. Nothing existing is changed or removed.
--   * lead_stages: where a business sits on the Pipeline when someone moves it by hand (Proposal sent, Won, ...).
--     Without a row, the app works the stage out from the call result, as before. Everyone signed in can read and
--     move cards (the pipeline is shared work); writes go through lead_stage_set() and show in Activity.
--   * lead_guard(): for a list of businesses, the latest call by a teammate in the last 14 days and the latest
--     "not interested" (call log or the business's result). Read-only; runs as the caller.
--   * app_status + me_status_report(): each app reports its version and sync state. Only admins (and the person
--     themselves) can read it. team_health() gives admins that list plus which database updates have been run.

-- ---------------------------------------------------------------- pipeline stages
create table if not exists public.lead_stages (
  lead_id    text primary key references public.leads(id) on delete cascade,
  stage      text not null check (stage in ('called','interested','meeting','proposal','won','lost')),
  updated_by uuid references public.profiles(id) on delete set null default auth.uid(),
  updated_at timestamptz not null default now()
);
alter table public.lead_stages enable row level security;
drop policy if exists lead_stages_read on public.lead_stages;
create policy lead_stages_read on public.lead_stages for select to authenticated using (public.is_active());
-- no insert/update/delete policies: writes only through lead_stage_set()

create or replace function public.lead_stage_list() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('lead_id', s.lead_id, 'stage', s.stage, 'updated_by', s.updated_by, 'updated_at', s.updated_at)), '[]'::jsonb)
  from public.lead_stages s
$$;

-- p_stage: called | interested | meeting | proposal | won | lost, or '' to go back to the automatic stage
create or replace function public.lead_stage_set(p_lead text, p_stage text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); nm text; who text; lbl text;
begin
  if me is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select name into nm from public.leads where id = p_lead;
  if nm is null then raise exception 'That business was not found'; end if;
  p_stage := coalesce(p_stage, '');
  if p_stage = '' then
    delete from public.lead_stages where lead_id = p_lead;
    return jsonb_build_object('ok', true, 'lead_id', p_lead, 'stage', null);
  end if;
  lbl := case p_stage when 'called' then 'Called' when 'interested' then 'Interested' when 'meeting' then 'Meeting'
                      when 'proposal' then 'Proposal sent' when 'won' then 'Won' when 'lost' then 'Lost' end;
  if lbl is null then raise exception 'That stage is not valid'; end if;
  insert into public.lead_stages (lead_id, stage, updated_by) values (p_lead, p_stage, me)
  on conflict (lead_id) do update set stage = excluded.stage, updated_by = me, updated_at = now();
  select display_name into who from public.profiles where id = me;
  insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
  values (me, 'pipeline', who || ' moved ' || nm || ' to ' || lbl, 'leads', p_lead);
  return jsonb_build_object('ok', true, 'lead_id', p_lead, 'stage', p_stage);
end $$;
revoke all on function public.lead_stage_set(text, text) from public;
grant execute on function public.lead_stage_set(text, text) to authenticated;
drop trigger if exists audit_lead_stages on public.lead_stages;
create trigger audit_lead_stages after insert or update or delete on public.lead_stages for each row execute function public.audit_row();

-- ---------------------------------------------------------------- duplicate / do-not-call guard
create index if not exists call_log_lead_idx on public.call_log (lead_id);
create index if not exists call_log_phone_key_idx on public.call_log ((right(regexp_replace(coalesce(phone, ''), '\D', '', 'g'), 10)));

-- p_leads: [{"id": "<lead id>", "key": "<last 10 digits of the phone>"}]  (up to 300)
create or replace function public.lead_guard(p_leads jsonb) returns jsonb
language sql stable security invoker set search_path = '' as $$
  with q as (
    select x->>'id' as id, nullif(right(regexp_replace(coalesce(x->>'key', ''), '\D', '', 'g'), 10), '') as k
    from jsonb_array_elements(case when jsonb_typeof(p_leads) = 'array' then p_leads else '[]'::jsonb end) with ordinality as t(x, n)
    where n <= 300
  ), hits as (
    select q.id, c.started_at, c.outcome, c.employee_id from q join public.call_log c on c.lead_id = q.id
    where c.started_at > now() - interval '365 days'
    union
    select q.id, c.started_at, c.outcome, c.employee_id from q join public.call_log c
      on q.k is not null and length(q.k) >= 7 and right(regexp_replace(coalesce(c.phone, ''), '\D', '', 'g'), 10) = q.k
    where c.started_at > now() - interval '365 days'
  ), recent as (
    select distinct on (id) id, started_at, outcome, employee_id from hits
    where employee_id is distinct from auth.uid() and started_at > now() - interval '14 days'
    order by id, started_at desc
  ), dnc as (
    select distinct on (id) id, at, who from (
      select id, started_at as at, employee_id as who from hits where outcome = 'not_interested'
      union all
      select q.id, coalesce(l.called_at, l.updated_at), l.called_by from q join public.leads l on l.id = q.id where l.status = 'red'
    ) z order by id, at desc nulls last
  )
  select coalesce(jsonb_agg(jsonb_build_object(
      'id', q.id,
      'last_at', r.started_at, 'last_outcome', r.outcome, 'last_by', r.employee_id, 'last_name', pr.display_name,
      'dnc_at', d.at, 'dnc_by', d.who, 'dnc_name', pd.display_name)), '[]'::jsonb)
  from q
  left join recent r on r.id = q.id left join public.profiles pr on pr.id = r.employee_id
  left join dnc d on d.id = q.id left join public.profiles pd on pd.id = d.who
  where r.id is not null or d.id is not null
$$;

-- ---------------------------------------------------------------- app status + admin health page
create table if not exists public.app_status (
  user_id     uuid primary key references public.profiles(id) on delete cascade,
  version     text not null default '' check (length(version) <= 40),
  platform    text not null default '' check (length(platform) <= 40),
  sync_state  text not null default '' check (length(sync_state) <= 40),
  pending     integer not null default 0 check (pending >= 0),
  last_error  text not null default '' check (length(last_error) <= 300),
  updated_at  timestamptz not null default now()
);
alter table public.app_status enable row level security;
drop policy if exists app_status_read on public.app_status;
create policy app_status_read on public.app_status for select to authenticated
  using (public.is_active() and (user_id = auth.uid() or public.is_admin()));
-- no insert/update/delete policies: writes only through me_status_report()

create or replace function public.me_status_report(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if jsonb_typeof(p) is distinct from 'object' then raise exception 'Nothing to report'; end if;
  insert into public.app_status (user_id, version, platform, sync_state, pending, last_error, updated_at)
  values (me, left(coalesce(p->>'version', ''), 40), left(coalesce(p->>'platform', ''), 40), left(coalesce(p->>'sync_state', ''), 40),
          greatest(0, least(1000000, coalesce((p->>'pending')::integer, 0))), left(coalesce(p->>'last_error', ''), 300), now())
  on conflict (user_id) do update set version = excluded.version, platform = excluded.platform, sync_state = excluded.sync_state,
    pending = excluded.pending, last_error = excluded.last_error, updated_at = now();
  return jsonb_build_object('ok', true);
exception when invalid_text_representation or numeric_value_out_of_range then
  raise exception 'Pending must be a number';
end $$;
revoke all on function public.me_status_report(jsonb) from public;
grant execute on function public.me_status_report(jsonb) to authenticated;

create or replace function public.team_health() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare col boolean; tab boolean; u jsonb; banner boolean;
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
    '17', true);
  return jsonb_build_object('updates', u, 'checked_at', now(), 'people', coalesce((
    select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'username', p.username, 'role', p.role, 'active', p.active,
                                        'last_seen', p.last_seen, 'version', s.version, 'platform', s.platform, 'sync_state', s.sync_state,
                                        'pending', s.pending, 'last_error', s.last_error, 'reported_at', s.updated_at)
                     order by p.active desc, p.display_name)
    from public.profiles p left join public.app_status s on s.user_id = p.id), '[]'::jsonb));
end $$;
revoke all on function public.team_health() from public;
grant execute on function public.team_health() to authenticated;
