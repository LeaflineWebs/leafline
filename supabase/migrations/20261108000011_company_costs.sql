-- Leafline 11.10 - 11th database update: company costs.
-- Admins record company expenses (for example software subscriptions or website hosting). Each cost is taken off
-- the money made that month and off one person's money on the leaderboard (the person it is charged to).
-- Everyone on the team can see the costs; only administrators can add or remove them.
-- Safe to run more than once. Adds one table and three functions; nothing existing is changed or removed.

create table if not exists public.expenses (
  id         uuid primary key default gen_random_uuid(),
  label      text not null check (length(btrim(label)) between 1 and 80),
  amount     numeric(12,2) not null check (amount > 0 and amount <= 1000000),
  spent_on   date not null default current_date,
  charged_to uuid references public.profiles(id) on delete set null,
  created_by uuid not null references public.profiles(id) default auth.uid(),
  created_at timestamptz not null default now()
);
create index if not exists expenses_spent_on_idx on public.expenses (spent_on);
alter table public.expenses enable row level security;

-- read: every active teammate. No insert/update/delete policies: changes only go through the admin-only functions below.
drop policy if exists expenses_read on public.expenses;
create policy expenses_read on public.expenses for select to authenticated using (public.is_active());

-- every change is recorded in the audit log (who added or removed which cost)
drop trigger if exists audit_expenses on public.expenses;
create trigger audit_expenses after insert or update or delete on public.expenses for each row execute function public.audit_row();

-- list: runs as the caller, so the read policy applies
create or replace function public.exp_list() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', e.id, 'label', e.label, 'amount', e.amount, 'spent_on', e.spent_on,
           'charged_to', e.charged_to, 'charged_name', c.display_name,
           'created_by', e.created_by, 'created_name', b.display_name, 'created_at', e.created_at)
         order by e.spent_on desc, e.created_at desc), '[]'::jsonb)
  from public.expenses e
  left join public.profiles c on c.id = e.charged_to
  left join public.profiles b on b.id = e.created_by
$$;

create or replace function public.exp_add(p_label text, p_amount numeric, p_on date, p_to uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.expenses; who uuid := coalesce(p_to, auth.uid());
begin
  if auth.uid() is null or not public.is_active() or not public.is_admin() then raise exception 'Only an administrator can add company costs'; end if;
  if p_label is null or length(btrim(p_label)) not between 1 and 80 then raise exception 'Describe the cost in 1 to 80 characters'; end if;
  if p_amount is null or p_amount <= 0 or p_amount > 1000000 then raise exception 'Enter an amount above 0'; end if;
  if not exists (select 1 from public.profiles where id = who and active) then raise exception 'Pick an active teammate to charge it to'; end if;
  insert into public.expenses (label, amount, spent_on, charged_to, created_by)
  values (btrim(p_label), round(p_amount, 2), coalesce(p_on, current_date), who, auth.uid())
  returning * into r;
  return jsonb_build_object('id', r.id);
end $$;

create or replace function public.exp_delete(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() or not public.is_admin() then raise exception 'Only an administrator can remove company costs'; end if;
  delete from public.expenses where id = p_id;
  if not found then raise exception 'That cost was already removed'; end if;
  return jsonb_build_object('ok', true);
end $$;

revoke all on function public.exp_list() from public, anon;
revoke all on function public.exp_add(text, numeric, date, uuid) from public, anon;
revoke all on function public.exp_delete(uuid) from public, anon;
grant execute on function public.exp_list() to authenticated;
grant execute on function public.exp_add(text, numeric, date, uuid) to authenticated;
grant execute on function public.exp_delete(uuid) to authenticated;
