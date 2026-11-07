-- Sixth migration (Leafline 11.1). Run AFTER migration 5. Safe to run more than once.
--  A. Old calls count again: calls from before the call log existed (the imported history and any result
--     marked before logging started) are added to the team numbers and the leaderboard.
--  B. Credit can be moved to the right person (for example when someone booked a meeting for a teammate).
--
-- Who may move credit:
--   * the person who has it now (to give it to someone),
--   * the person it is for (to claim it),
--   * an admin.
-- Every move is written to the team Activity feed, so everyone can see it.
-- Calls stay with whoever dialled. Only the result (meeting booked / sale) moves.

alter table public.call_log add column if not exists credited_to uuid references public.profiles(id);

-- Team numbers: calls, connections and prospects count for the caller. Meetings and sales count for whoever has the credit.
create or replace function public.daily_stats(p_from date, p_to date)
returns table(day date, employee_id uuid, calls bigint, connections bigint, prospects bigint, meetings bigint, sales bigint)
language sql stable security invoker set search_path = '' as $$
  with c as (
    select (x.started_at at time zone 'America/Toronto')::date as d, x.employee_id as e, coalesce(x.credited_to, x.employee_id) as cr, x.outcome, x.lead_id
    from public.call_log x
    where (x.started_at at time zone 'America/Toronto')::date between p_from and p_to   -- old (imported) calls count too
  ), u as (
    select d, e as who, count(*) as calls,
           count(*) filter (where outcome in ('interested','not_interested','follow_up','meeting_booked','sale_completed')) as connections,
           count(distinct lead_id) as prospects, 0::bigint as meetings, 0::bigint as sales
    from c group by 1, 2
    union all
    select d, cr, 0, 0, 0, count(*) filter (where outcome = 'meeting_booked'), count(*) filter (where outcome = 'sale_completed')
    from c where outcome in ('meeting_booked','sale_completed') group by 1, 2
  )
  select d, who, sum(calls)::bigint, sum(connections)::bigint, sum(prospects)::bigint, sum(meetings)::bigint, sum(sales)::bigint
  from u group by 1, 2
$$;

-- The deal guard from migration 5, plus a door for reassign_credit() below.
create or replace function public.guard_deal_owner() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or public.is_admin() or current_setting('leafline.credit', true) = '1' then return new; end if;
  if tg_op = 'INSERT' then
    if new.owner_id is not null and new.owner_id <> auth.uid() then raise exception 'You can only add deals for yourself'; end if;
    new.owner_id := coalesce(new.owner_id, auth.uid());
  elsif new.owner_id is distinct from old.owner_id then
    raise exception 'Use "Credited to" to move a deal to someone else';
  end if;
  return new;
end $$;

create or replace function public.reassign_credit(p_kind text, p_id text, p_to uuid)
returns json language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); cur uuid; what text; who_me text; who_to text;
begin
  if me is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select display_name into who_to from public.profiles where id = p_to and active;
  if who_to is null then raise exception 'Pick an active teammate'; end if;
  if p_kind = 'lead' then
    select called_by, name into cur, what from public.leads where id = p_id;
    if not found then raise exception 'That business was not found'; end if;
  elsif p_kind = 'deal' then
    select owner_id, client into cur, what from public.deals where id = p_id::uuid;
    if not found then raise exception 'That deal was not found'; end if;
  else
    raise exception 'Unknown item';
  end if;
  if cur is not distinct from p_to then return json_build_object('ok', true, 'unchanged', true); end if;
  if not (public.is_admin() or cur is null or cur = me or p_to = me) then
    raise exception 'Only the person who has it, the person it is for, or an admin can move it';
  end if;
  if p_kind = 'lead' then
    update public.leads set called_by = p_to where id = p_id;
    update public.call_log set credited_to = p_to where lead_id = p_id and outcome in ('meeting_booked','sale_completed');
  else
    perform set_config('leafline.credit', '1', true);
    update public.deals set owner_id = p_to where id = p_id::uuid;
    perform set_config('leafline.credit', '0', true);
  end if;
  select display_name into who_me from public.profiles where id = me;
  insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
  values (me, 'credit', case when p_to = me then who_me || ' took credit for ' || what
                             else who_me || ' gave ' || what || ' to ' || who_to end,
          case when p_kind = 'lead' then 'leads' else 'deals' end, p_id);
  return json_build_object('ok', true);
end $$;
revoke all on function public.reassign_credit(text, text, uuid) from public;
grant execute on function public.reassign_credit(text, text, uuid) to authenticated;

-- ---------------------------------------------------------------- A. bring the old calls back into the numbers
-- 1. Imported calls with no person attached get the person the business is credited to.
update public.call_log c set employee_id = l.called_by
from public.leads l
where c.lead_id = l.id and c.employee_id is null and l.called_by is not null;

-- 2. Every called business that has NO call record at all gets one, dated when it was called and credited to
--    whoever called it. Uses a fixed id per business, so running this file again never adds doubles.
--    (The activity-feed trigger is paused so the feed isn't flooded with hundreds of old calls.)
alter table public.call_log disable trigger feed_call_log;
insert into public.call_log (client_op_id, lead_id, employee_id, phone, started_at, outcome, notes, source)
select md5('backfill-call:' || l.id)::uuid, l.id, l.called_by, coalesce(l.phone, ''), l.called_at,
       case l.status when 'green' then 'meeting_booked' when 'yellow' then 'interested' when 'orange' then 'no_answer' else 'not_interested' end,
       coalesce(l.notes, ''), 'backfill'
from public.leads l
where l.status in ('green','yellow','orange','red') and l.called_by is not null and l.called_at is not null
  and not exists (select 1 from public.call_log c where c.lead_id = l.id)
on conflict (client_op_id) do nothing;
alter table public.call_log enable trigger feed_call_log;

-- Check: how many calls each person now has (shown under the query when you press Run)
select p.display_name, count(c.*) as calls_on_record
from public.profiles p left join public.call_log c on c.employee_id = p.id
group by p.display_name order by calls_on_record desc;
