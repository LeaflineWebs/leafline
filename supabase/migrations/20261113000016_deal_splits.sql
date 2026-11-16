-- 16th update (Leafline 11.18): profit splits. Safe to run more than once. Nothing existing is changed or removed.
-- When a payment is confirmed, its money can be split between teammates by percent (e.g. Omar 60%, Jay 40%).
--   * A split is kept for that one payment (pay_key "YYYY-MM-DD:upfront" / "YYYY-MM-DD:monthly"), and also as the
--     deal's default (pay_key ''), which every later payment of that deal follows until someone changes it.
--   * With no split, a payment counts 100% for the person the deal is credited to (as before).
--   * Everyone signed in can read splits (the leaderboard needs them). Nobody can write the table directly:
--     only deal_split_set() below, which checks the rules.
-- Who may set a split: an admin, or the person the deal is credited to.

create table if not exists public.deal_splits (
  deal_id    uuid not null references public.deals(id) on delete cascade,
  pay_key    text not null default '' check (pay_key ~ '^([0-9]{4}-[0-9]{2}-[0-9]{2}:(upfront|monthly))?$'),
  shares     jsonb not null check (jsonb_typeof(shares) = 'array' and jsonb_array_length(shares) between 1 and 8),
  updated_by uuid references public.profiles(id) on delete set null default auth.uid(),
  updated_at timestamptz not null default now(),
  primary key (deal_id, pay_key)
);
alter table public.deal_splits enable row level security;
drop policy if exists deal_splits_read on public.deal_splits;
create policy deal_splits_read on public.deal_splits for select to authenticated using (public.is_active());
-- no insert/update/delete policies: writes only through deal_split_set()

-- p_shares: [{"id": "<teammate uuid>", "pct": 60}, {"id": "...", "pct": 40}]   (1 to 8 people, adds up to exactly 100)
-- p_key:    the payment ("YYYY-MM-DD:upfront" or "YYYY-MM-DD:monthly"), or '' for the deal's default only
-- p_default: also make this the deal's default (later payments follow it)
create or replace function public.deal_split_set(p_deal uuid, p_key text, p_shares jsonb, p_default boolean default true)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); d record; s jsonb; clean jsonb := '[]'::jsonb; total numeric := 0; pct numeric;
        pid uuid; seen uuid[] := '{}'; nm text; who_me text; names text := '';
begin
  if me is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select id, client, owner_id into d from public.deals where id = p_deal;
  if not found then raise exception 'That deal was not found'; end if;
  if not (public.is_admin() or d.owner_id = me) then
    raise exception 'Only an admin or the person this deal is credited to can split it';
  end if;
  p_key := coalesce(p_key, '');
  if p_key !~ '^([0-9]{4}-[0-9]{2}-[0-9]{2}:(upfront|monthly))?$' then raise exception 'That payment is not valid'; end if;
  if jsonb_typeof(p_shares) is distinct from 'array' or jsonb_array_length(p_shares) not between 1 and 8 then
    raise exception 'Split it between 1 and 8 people';
  end if;
  for s in select * from jsonb_array_elements(p_shares) loop
    begin
      pid := (s->>'id')::uuid; pct := (s->>'pct')::numeric;
    exception when others then raise exception 'Each part needs a teammate and a percent';
    end;
    if pid is null or pct is null then raise exception 'Each part needs a teammate and a percent'; end if;
    if pct <= 0 or pct > 100 or pct <> round(pct, 2) then raise exception 'Each percent must be more than 0 and at most 100 (up to 2 decimals)'; end if;
    if pid = any(seen) then raise exception 'Each teammate can only be in the split once'; end if;
    select display_name into nm from public.profiles where id = pid and active;
    if nm is null then raise exception 'Pick active teammates only'; end if;
    seen := seen || pid; total := total + pct;
    clean := clean || jsonb_build_array(jsonb_build_object('id', pid, 'pct', pct));
    names := names || case when names = '' then '' else ', ' end || nm || ' ' || (case when pct = trunc(pct) then trunc(pct)::text else rtrim(rtrim(pct::text, '0'), '.') end) || '%';
  end loop;
  if total <> 100 then raise exception 'The percents must add up to 100 (they add up to %)', total; end if;
  if p_key <> '' then
    insert into public.deal_splits (deal_id, pay_key, shares, updated_by) values (p_deal, p_key, clean, me)
    on conflict (deal_id, pay_key) do update set shares = excluded.shares, updated_by = me, updated_at = now();
  end if;
  if p_key = '' or coalesce(p_default, true) then
    insert into public.deal_splits (deal_id, pay_key, shares, updated_by) values (p_deal, '', clean, me)
    on conflict (deal_id, pay_key) do update set shares = excluded.shares, updated_by = me, updated_at = now();
  end if;
  select display_name into who_me from public.profiles where id = me;
  insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
  values (me, 'credit', who_me || ' split ' || d.client || ': ' || names, 'deals', p_deal::text);   -- percents only, never amounts
  return jsonb_build_object('ok', true, 'deal_id', p_deal, 'pay_key', p_key, 'shares', clean);
end $$;
revoke all on function public.deal_split_set(uuid, text, jsonb, boolean) from public;
grant execute on function public.deal_split_set(uuid, text, jsonb, boolean) to authenticated;

-- changes to splits are kept in the audit log like every other table
drop trigger if exists audit_deal_splits on public.deal_splits;
create trigger audit_deal_splits after insert or update or delete on public.deal_splits for each row execute function public.audit_row();
