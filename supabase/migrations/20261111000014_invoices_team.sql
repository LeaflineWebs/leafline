-- Leafline 11.15 - 14th database update: invoices, invoice templates, and team profile cards.
--
-- * Invoices: every active teammate can create invoices and sees the ones they created. Administrators see every
--   invoice, mark invoices paid (with the payment details), void them, edit the templates and the invoice settings
--   (company details, tax, e-Transfer email). Totals are always calculated here in the database, never trusted from the app.
-- * Templates: reusable starting points (items, payment terms, notes, terms and conditions). Only admins change them;
--   they are archived, never deleted, so old invoices keep pointing at them.
-- * Team cards: department, responsibilities, skills and work contact details on each profile. You edit your own;
--   admins can edit anyone's. Every active teammate can see them (same rule as the rest of the profile).
--
-- Safe to run more than once. Nothing existing is changed or removed: it adds columns, two tables and functions.

-- ---------------------------------------------------------------- team cards
alter table public.profiles add column if not exists department text check (department is null or length(department) <= 60);
alter table public.profiles add column if not exists responsibilities text check (responsibilities is null or length(responsibilities) <= 600);
alter table public.profiles add column if not exists skills text check (skills is null or length(skills) <= 300);
alter table public.profiles add column if not exists work_phone text check (work_phone is null or length(work_phone) <= 30);
alter table public.profiles add column if not exists work_email text check (work_email is null or (length(work_email) <= 160 and work_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'));

-- every teammate's card (runs as the caller, so only signed-in active teammates get anything back)
create or replace function public.team_cards() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', p.id, 'username', p.username, 'name', p.display_name, 'role', p.role, 'active', p.active,
           'title', p.title, 'department', p.department, 'responsibilities', p.responsibilities, 'skills', p.skills,
           'work_phone', p.work_phone, 'work_email', p.work_email, 'joined', p.created_at, 'last_seen', p.last_seen)
         order by p.display_name), '[]'::jsonb)
  from public.profiles p
$$;

create or replace function public.team_card_set(p_id uuid, p_department text, p_responsibilities text, p_skills text, p_phone text, p_email text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare dep text := nullif(btrim(coalesce(p_department, '')), ''); res text := nullif(btrim(coalesce(p_responsibilities, '')), '');
        sk text := nullif(btrim(coalesce(p_skills, '')), ''); ph text := nullif(btrim(coalesce(p_phone, '')), ''); em text := nullif(lower(btrim(coalesce(p_email, ''))), '');
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p_id is null or (p_id <> auth.uid() and not public.is_admin()) then raise exception 'You can only change your own card'; end if;
  if length(dep) > 60 then raise exception 'Keep the department under 60 characters'; end if;
  if length(res) > 600 then raise exception 'Keep the responsibilities under 600 characters'; end if;
  if length(sk) > 300 then raise exception 'Keep the skills under 300 characters'; end if;
  if length(ph) > 30 or ph !~ '^[0-9+()\-. ext]+$' then raise exception 'That phone number is not valid'; end if;
  if length(em) > 160 or em !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'That email address is not valid'; end if;
  update public.profiles set department = dep, responsibilities = res, skills = sk, work_phone = ph, work_email = em where id = p_id;
  if not found then raise exception 'That teammate was not found'; end if;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- invoice templates
create table if not exists public.invoice_templates (
  id            uuid primary key default gen_random_uuid(),
  name          text not null check (length(btrim(name)) between 1 and 80),
  category      text not null default '' check (length(category) <= 60),
  summary       text not null default '' check (length(summary) <= 300),
  items         jsonb not null default '[]'::jsonb check (jsonb_typeof(items) = 'array'),
  payment_terms text not null default '' check (length(payment_terms) <= 2000),
  notes         text not null default '' check (length(notes) <= 4000),
  terms         text not null default '' check (length(terms) <= 20000),
  due_days      integer not null default 14 check (due_days between 0 and 365),
  tax_rate      numeric(6,3) check (tax_rate is null or tax_rate between 0 and 30),
  source        text not null default '' check (length(source) <= 200),   -- the document it was built from
  archived      boolean not null default false,
  sort          integer not null default 0,
  created_by    uuid references public.profiles(id) default auth.uid(),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  updated_by    uuid,
  version       integer not null default 1
);

-- ---------------------------------------------------------------- invoices
create table if not exists public.invoices (
  id             uuid primary key default gen_random_uuid(),
  number         text not null unique check (length(number) between 1 and 40),
  status         text not null default 'draft' check (status in ('draft', 'sent', 'paid', 'void')),
  template_id    uuid references public.invoice_templates(id) on delete set null,
  lead_id        text references public.leads(id) on delete set null,
  deal_id        uuid references public.deals(id) on delete set null,
  client_name    text not null check (length(btrim(client_name)) between 1 and 120),
  client_contact text not null default '' check (length(client_contact) <= 120),
  client_email   text not null default '' check (length(client_email) <= 160),
  client_phone   text not null default '' check (length(client_phone) <= 40),
  client_address text not null default '' check (length(client_address) <= 400),
  issue_date     date not null default current_date,
  due_date       date not null,
  currency       text not null default 'CAD' check (currency in ('CAD', 'USD')),
  items          jsonb not null check (jsonb_typeof(items) = 'array'),
  discount_kind  text not null default 'none' check (discount_kind in ('none', 'percent', 'amount')),
  discount_value numeric(12,2) not null default 0 check (discount_value >= 0),
  tax_label      text not null default 'HST' check (length(tax_label) <= 20),
  tax_rate       numeric(6,3) not null default 0 check (tax_rate between 0 and 30),
  subtotal       numeric(12,2) not null default 0,
  discount_total numeric(12,2) not null default 0,
  tax_total      numeric(12,2) not null default 0,
  total          numeric(12,2) not null default 0,
  payment_terms  text not null default '' check (length(payment_terms) <= 2000),
  notes          text not null default '' check (length(notes) <= 4000),
  terms          text not null default '' check (length(terms) <= 20000),
  sent_at        timestamptz,
  paid_amount    numeric(12,2),
  paid_on        date,
  paid_method    text check (paid_method is null or length(paid_method) <= 40),
  paid_ref       text check (paid_ref is null or length(paid_ref) <= 80),
  paid_note      text check (paid_note is null or length(paid_note) <= 400),
  paid_by        uuid references public.profiles(id),
  voided_at      timestamptz,
  void_reason    text check (void_reason is null or length(void_reason) <= 200),
  created_by     uuid not null references public.profiles(id) default auth.uid(),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  updated_by     uuid,
  version        integer not null default 1,
  check (due_date >= issue_date)
);
create index if not exists invoices_created_by_idx on public.invoices (created_by);
create index if not exists invoices_issue_idx on public.invoices (issue_date desc);
create index if not exists invoices_status_idx on public.invoices (status);

alter table public.invoice_templates enable row level security;
alter table public.invoices enable row level security;

-- read: templates for every active teammate; invoices for admins, or the person who created them.
-- No insert/update/delete policies: every change goes through the checked functions below.
drop policy if exists invoice_templates_read on public.invoice_templates;
create policy invoice_templates_read on public.invoice_templates for select to authenticated using (public.is_active());
drop policy if exists invoices_read on public.invoices;
create policy invoices_read on public.invoices for select to authenticated using (public.is_active() and (public.is_admin() or created_by = auth.uid()));

drop trigger if exists touch_invoices on public.invoices;
create trigger touch_invoices before update on public.invoices for each row execute function public.touch_row();
drop trigger if exists touch_invoice_templates on public.invoice_templates;
create trigger touch_invoice_templates before update on public.invoice_templates for each row execute function public.touch_row();
drop trigger if exists audit_invoices on public.invoices;
create trigger audit_invoices after insert or update or delete on public.invoices for each row execute function public.audit_row();
drop trigger if exists audit_invoice_templates on public.invoice_templates;
create trigger audit_invoice_templates after insert or update or delete on public.invoice_templates for each row execute function public.audit_row();

-- Activity feed: who issued an invoice and when one was paid. No amounts (the feed is visible to the whole team).
create or replace function public.inv_feed() returns trigger
language plpgsql security definer set search_path = '' as $$
declare who text;
begin
  if auth.uid() is null then return null; end if;
  select display_name into who from public.profiles where id = auth.uid();
  if new.status = 'sent' and (tg_op = 'INSERT' or old.status = 'draft') then
    insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
    values (auth.uid(), 'invoice', who || ' issued invoice ' || new.number || ' to ' || new.client_name, 'invoices', new.id::text);
  elsif tg_op = 'UPDATE' and new.status = 'paid' and old.status <> 'paid' then
    insert into public.activity(employee_id, kind, summary, ref_table, ref_id)
    values (auth.uid(), 'invoice', 'Invoice ' || new.number || ' (' || new.client_name || ') was paid', 'invoices', new.id::text);
  end if;
  return null;
end $$;
drop trigger if exists feed_invoices on public.invoices;
create trigger feed_invoices after insert or update on public.invoices for each row execute function public.inv_feed();

-- ---------------------------------------------------------------- helpers
create or replace function public.inv_today() returns date
language sql stable set search_path = '' as $$ select (now() at time zone 'America/Toronto')::date $$;

-- Cleans and checks the line items: [{description, details, qty, unit_price, taxable}]. Blank rows are dropped.
create or replace function public.inv_items(p jsonb) returns jsonb
language plpgsql immutable set search_path = '' as $$
declare e jsonb; res jsonb := '[]'::jsonb; d text; det text; q numeric; u numeric; n integer := 0;
begin
  if p is null or jsonb_typeof(p) <> 'array' then raise exception 'Add at least one item'; end if;
  for e in select x from jsonb_array_elements(p) as t(x) loop
    if jsonb_typeof(e) <> 'object' then raise exception 'One of the items is not valid'; end if;
    d := btrim(coalesce(e->>'description', '')); det := btrim(coalesce(e->>'details', ''));
    begin
      q := round(coalesce(nullif(btrim(e->>'qty'), ''), '1')::numeric, 2);
      u := round(coalesce(nullif(btrim(e->>'unit_price'), ''), '0')::numeric, 2);
    exception when others then raise exception 'Quantities and prices must be numbers';
    end;
    if d = '' and det = '' and u = 0 then continue; end if;
    if d = '' then raise exception 'Every item needs a description'; end if;
    if length(d) > 200 then raise exception 'Keep each item description under 200 characters'; end if;
    if length(det) > 2000 then raise exception 'Keep each item''s details under 2000 characters'; end if;
    if q <= 0 or q > 100000 then raise exception 'Quantities must be above 0'; end if;
    if u < 0 or u > 1000000 then raise exception 'Prices must be between $0 and $1,000,000'; end if;
    n := n + 1;
    if n > 60 then raise exception 'An invoice can have at most 60 items'; end if;
    res := res || jsonb_build_array(jsonb_build_object('description', d, 'details', det, 'qty', q, 'unit_price', u,
                                                       'taxable', coalesce((e->>'taxable')::boolean, true)));
  end loop;
  return res;
end $$;

-- Totals. Discount comes off the subtotal; tax is charged on the taxable items after their share of the discount.
create or replace function public.inv_totals(p_items jsonb, p_kind text, p_value numeric, p_rate numeric) returns jsonb
language plpgsql immutable set search_path = '' as $$
declare sub numeric := 0; tx numeric := 0; disc numeric := 0; base numeric := 0; tax numeric := 0; e jsonb; line numeric;
begin
  for e in select x from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) as t(x) loop
    line := round((e->>'qty')::numeric * (e->>'unit_price')::numeric, 2);
    sub := sub + line;
    if coalesce((e->>'taxable')::boolean, true) then tx := tx + line; end if;
  end loop;
  disc := case p_kind when 'percent' then round(sub * least(greatest(coalesce(p_value, 0), 0), 100) / 100, 2)
                      when 'amount' then least(round(greatest(coalesce(p_value, 0), 0), 2), sub) else 0 end;
  base := case when sub > 0 then tx - round(disc * tx / sub, 2) else 0 end;
  tax := round(base * coalesce(p_rate, 0) / 100, 2);
  return jsonb_build_object('subtotal', sub, 'discount', disc, 'tax', tax, 'total', sub - disc + tax);
end $$;

-- Invoice settings live in the existing settings table (key 'invoice'); every active teammate can read them.
create or replace function public.inv_settings() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select jsonb_build_object(
    'company_name', 'Leafline Web Services', 'company_address', '', 'company_phone', '', 'company_email', '', 'company_website', '',
    'tax_label', 'HST', 'tax_rate', 0, 'tax_number', '', 'currency', 'CAD', 'number_prefix', 'LF', 'default_due_days', 14,
    'etransfer_email', '', 'etransfer_name', '', 'payment_note', '', 'footer', 'Thank you for your business.')
    || coalesce((select s.value from public.settings s where s.key = 'invoice'), '{}'::jsonb)
  where public.is_active()
$$;

create or replace function public.inv_settings_set(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare cur jsonb; k text; v jsonb; out jsonb := '{}'::jsonb; s text;
        lim constant jsonb := '{"company_name":80,"company_address":300,"company_phone":40,"company_email":160,"company_website":160,
                                "tax_label":20,"tax_number":40,"etransfer_email":160,"etransfer_name":80,"payment_note":1000,"footer":300}';
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Only an administrator can change the invoice settings'; end if;
  if p is null or jsonb_typeof(p) <> 'object' then raise exception 'Nothing to save'; end if;
  cur := coalesce((select value from public.settings where key = 'invoice'), '{}'::jsonb);
  for k, v in select * from jsonb_each(p) loop
    if lim ? k then
      s := btrim(coalesce(v #>> '{}', ''));
      if length(s) > (lim->>k)::int then raise exception '% is too long', replace(k, '_', ' '); end if;
      if k in ('etransfer_email', 'company_email') and s <> '' and s !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'That email address is not valid'; end if;
      out := out || jsonb_build_object(k, s);
    elsif k = 'tax_rate' then
      if jsonb_typeof(v) <> 'number' or (v #>> '{}')::numeric < 0 or (v #>> '{}')::numeric > 30 then raise exception 'The tax rate must be between 0 and 30 percent'; end if;
      out := out || jsonb_build_object(k, round((v #>> '{}')::numeric, 3));
    elsif k = 'default_due_days' then
      if jsonb_typeof(v) <> 'number' or (v #>> '{}')::numeric not between 0 and 365 then raise exception 'Days to pay must be between 0 and 365'; end if;
      out := out || jsonb_build_object(k, (v #>> '{}')::numeric::int);
    elsif k = 'number_prefix' then
      if coalesce(v #>> '{}', '') !~ '^[A-Z0-9]{1,8}$' then raise exception 'The invoice number prefix must be 1 to 8 capital letters or digits'; end if;
      out := out || jsonb_build_object(k, v #>> '{}');
    elsif k = 'currency' then
      if coalesce(v #>> '{}', '') not in ('CAD', 'USD') then raise exception 'The currency must be CAD or USD'; end if;
      out := out || jsonb_build_object(k, v #>> '{}');
    else raise exception 'Unknown setting: %', k;
    end if;
  end loop;
  insert into public.settings (key, value, updated_at) values ('invoice', cur || out, now())
  on conflict (key) do update set value = public.settings.value || out, updated_at = now();
  return public.inv_settings();
end $$;

-- Next number: PREFIX-YEAR-0001, counting up per prefix and year. Serialized so two people never get the same one.
create or replace function public.inv_next_number() returns text
language plpgsql security definer set search_path = '' as $$
declare pre text; yr text := to_char(public.inv_today(), 'YYYY'); n integer;
begin
  perform pg_advisory_xact_lock(hashtext('leafline_invoice_number'));
  pre := coalesce((select value->>'number_prefix' from public.settings where key = 'invoice'), 'LF');
  select coalesce(max(substring(number from '-(\d+)$')::int), 0) + 1 into n
  from public.invoices where number like pre || '-' || yr || '-%';
  return pre || '-' || yr || '-' || lpad(n::text, 4, '0');
end $$;

-- one invoice as the app sees it
create or replace function public.inv_json(i public.invoices, full_row boolean) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', i.id, 'number', i.number, 'status', i.status,
    'overdue', i.status = 'sent' and i.due_date < public.inv_today(),
    'template_id', i.template_id, 'template_name', (select t.name from public.invoice_templates t where t.id = i.template_id),
    'lead_id', i.lead_id, 'deal_id', i.deal_id,
    'client_name', i.client_name, 'client_contact', i.client_contact, 'client_email', i.client_email,
    'client_phone', i.client_phone, 'client_address', i.client_address,
    'issue_date', i.issue_date, 'due_date', i.due_date, 'currency', i.currency,
    'discount_kind', i.discount_kind, 'discount_value', i.discount_value, 'tax_label', i.tax_label, 'tax_rate', i.tax_rate,
    'subtotal', i.subtotal, 'discount_total', i.discount_total, 'tax_total', i.tax_total, 'total', i.total,
    'sent_at', i.sent_at, 'paid_amount', i.paid_amount, 'paid_on', i.paid_on, 'paid_method', i.paid_method, 'paid_ref', i.paid_ref,
    'paid_note', i.paid_note, 'paid_by_name', (select p.display_name from public.profiles p where p.id = i.paid_by),
    'voided_at', i.voided_at, 'void_reason', i.void_reason,
    'created_by', i.created_by, 'created_name', (select p.display_name from public.profiles p where p.id = i.created_by),
    'created_at', i.created_at, 'updated_at', i.updated_at, 'version', i.version, 'item_count', jsonb_array_length(i.items))
  || case when full_row then jsonb_build_object('items', i.items, 'payment_terms', i.payment_terms, 'notes', i.notes, 'terms', i.terms) else '{}'::jsonb end
$$;
revoke all on function public.inv_json(public.invoices, boolean) from public, anon, authenticated;

-- the caller may see this invoice (admin, or they made it)
create or replace function public.inv_mine(i public.invoices) returns boolean
language sql stable security definer set search_path = '' as $$ select public.is_active() and (public.is_admin() or i.created_by = auth.uid()) $$;
revoke all on function public.inv_mine(public.invoices) from public, anon, authenticated;

-- ---------------------------------------------------------------- invoice functions
create or replace function public.inv_list() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  return jsonb_build_object('today', public.inv_today(), 'admin', public.is_admin(),
    'invoices', coalesce((select jsonb_agg(public.inv_json(i, false) order by i.issue_date desc, i.created_at desc)
                          from public.invoices i where public.inv_mine(i)), '[]'::jsonb));
end $$;

create or replace function public.inv_get(p_id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare i public.invoices;
begin
  select * into i from public.invoices where id = p_id;
  if not found or not public.inv_mine(i) then raise exception 'That invoice was not found'; end if;
  return public.inv_json(i, true);
end $$;

-- Create (no id) or update (id + version). p_status: 'draft' or 'sent'.
create or replace function public.inv_save(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i public.invoices; it jsonb; tot jsonb; st text := coalesce(p->>'status', 'draft'); idt date; ddt date;
        cname text := btrim(coalesce(p->>'client_name', '')); dk text := coalesce(p->>'discount_kind', 'none');
        dv numeric; rate numeric; tid uuid; lid text; did uuid; cur text;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p is null or jsonb_typeof(p) <> 'object' then raise exception 'Nothing to save'; end if;
  if st not in ('draft', 'sent') then raise exception 'An invoice can only be saved as a draft or as issued'; end if;
  if cname = '' then raise exception 'Enter the client''s name'; end if;
  if length(cname) > 120 then raise exception 'Keep the client''s name under 120 characters'; end if;
  begin
    idt := coalesce(nullif(p->>'issue_date', '')::date, public.inv_today());
    ddt := nullif(p->>'due_date', '')::date;
    dv := round(coalesce(nullif(p->>'discount_value', '')::numeric, 0), 2);
    rate := round(coalesce(nullif(p->>'tax_rate', '')::numeric, 0), 3);
  exception when others then raise exception 'Check the dates, discount and tax rate';
  end;
  if ddt is null then raise exception 'Pick the date payment is due'; end if;
  if ddt < idt then raise exception 'The due date can''t be before the invoice date'; end if;
  if dk not in ('none', 'percent', 'amount') then raise exception 'That discount type is not valid'; end if;
  if dv < 0 or (dk = 'percent' and dv > 100) then raise exception 'A percent discount must be between 0 and 100'; end if;
  if dk = 'none' then dv := 0; end if;
  if rate < 0 or rate > 30 then raise exception 'The tax rate must be between 0 and 30 percent'; end if;
  cur := coalesce(nullif(p->>'currency', ''), 'CAD');
  if cur not in ('CAD', 'USD') then raise exception 'The currency must be CAD or USD'; end if;
  it := public.inv_items(p->'items');
  if jsonb_array_length(it) = 0 then raise exception 'Add at least one item'; end if;
  tot := public.inv_totals(it, dk, dv, rate);
  tid := nullif(p->>'template_id', '')::uuid; lid := nullif(p->>'lead_id', ''); did := nullif(p->>'deal_id', '')::uuid;
  if tid is not null and not exists (select 1 from public.invoice_templates where id = tid) then tid := null; end if;
  if lid is not null and not exists (select 1 from public.leads where id = lid) then lid := null; end if;
  if did is not null and not exists (select 1 from public.deals where id = did) then did := null; end if;
  if length(coalesce(p->>'client_contact', '')) > 120 or length(coalesce(p->>'client_email', '')) > 160 or length(coalesce(p->>'client_phone', '')) > 40
     or length(coalesce(p->>'client_address', '')) > 400 then raise exception 'Some of the client details are too long'; end if;
  if length(coalesce(p->>'payment_terms', '')) > 2000 or length(coalesce(p->>'notes', '')) > 4000 or length(coalesce(p->>'terms', '')) > 20000
     then raise exception 'The payment terms, notes or terms are too long'; end if;
  if length(coalesce(p->>'tax_label', 'HST')) > 20 then raise exception 'Keep the tax name under 20 characters'; end if;

  if nullif(p->>'id', '') is null then
    insert into public.invoices (number, status, template_id, lead_id, deal_id, client_name, client_contact, client_email, client_phone, client_address,
        issue_date, due_date, currency, items, discount_kind, discount_value, tax_label, tax_rate, subtotal, discount_total, tax_total, total,
        payment_terms, notes, terms, sent_at, created_by)
    values (public.inv_next_number(), st, tid, lid, did, cname, btrim(coalesce(p->>'client_contact', '')), btrim(coalesce(p->>'client_email', '')),
        btrim(coalesce(p->>'client_phone', '')), btrim(coalesce(p->>'client_address', '')), idt, ddt, cur, it, dk, dv,
        btrim(coalesce(p->>'tax_label', 'HST')), rate, (tot->>'subtotal')::numeric, (tot->>'discount')::numeric, (tot->>'tax')::numeric,
        (tot->>'total')::numeric, coalesce(p->>'payment_terms', ''), coalesce(p->>'notes', ''), coalesce(p->>'terms', ''),
        case when st = 'sent' then now() end, auth.uid())
    returning * into i;
  else
    select * into i from public.invoices where id = (p->>'id')::uuid for update;
    if not found or not public.inv_mine(i) then raise exception 'That invoice was not found'; end if;
    if i.status in ('paid', 'void') then raise exception 'A % invoice can''t be edited', i.status; end if;
    if nullif(p->>'version', '') is not null and (p->>'version')::int <> i.version then
      raise exception 'Someone else changed this invoice. Reopen it to see their changes' using errcode = '40001'; end if;
    update public.invoices set status = st, template_id = tid, lead_id = lid, deal_id = did, client_name = cname,
        client_contact = btrim(coalesce(p->>'client_contact', '')), client_email = btrim(coalesce(p->>'client_email', '')),
        client_phone = btrim(coalesce(p->>'client_phone', '')), client_address = btrim(coalesce(p->>'client_address', '')),
        issue_date = idt, due_date = ddt, currency = cur, items = it, discount_kind = dk, discount_value = dv,
        tax_label = btrim(coalesce(p->>'tax_label', 'HST')), tax_rate = rate,
        subtotal = (tot->>'subtotal')::numeric, discount_total = (tot->>'discount')::numeric, tax_total = (tot->>'tax')::numeric, total = (tot->>'total')::numeric,
        payment_terms = coalesce(p->>'payment_terms', ''), notes = coalesce(p->>'notes', ''), terms = coalesce(p->>'terms', ''),
        sent_at = case when st = 'sent' then coalesce(i.sent_at, now()) else null end
    where id = i.id returning * into i;
  end if;
  return public.inv_json(i, true);
end $$;

-- Copy any invoice you can see into a new draft, dated today, with the same number of days to pay.
create or replace function public.inv_duplicate(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i public.invoices; n public.invoices; t date := public.inv_today();
begin
  select * into i from public.invoices where id = p_id;
  if not found or not public.inv_mine(i) then raise exception 'That invoice was not found'; end if;
  insert into public.invoices (number, status, template_id, lead_id, deal_id, client_name, client_contact, client_email, client_phone, client_address,
      issue_date, due_date, currency, items, discount_kind, discount_value, tax_label, tax_rate, subtotal, discount_total, tax_total, total,
      payment_terms, notes, terms, created_by)
  values (public.inv_next_number(), 'draft', i.template_id, i.lead_id, i.deal_id, i.client_name, i.client_contact, i.client_email, i.client_phone,
      i.client_address, t, t + (i.due_date - i.issue_date), i.currency, i.items, i.discount_kind, i.discount_value, i.tax_label, i.tax_rate,
      i.subtotal, i.discount_total, i.tax_total, i.total, i.payment_terms, i.notes, i.terms, auth.uid())
  returning * into n;
  return public.inv_json(n, true);
end $$;

-- draft <-> issued (creator or admin); void (admin only). Paid invoices go back to issued with inv_unpay first.
create or replace function public.inv_set_status(p_id uuid, p_status text, p_reason text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i public.invoices;
begin
  select * into i from public.invoices where id = p_id for update;
  if not found or not public.inv_mine(i) then raise exception 'That invoice was not found'; end if;
  if p_status = 'void' then
    if not public.is_admin() then raise exception 'Only an administrator can void an invoice'; end if;
    if i.status = 'paid' then raise exception 'Mark it unpaid before voiding it'; end if;
    update public.invoices set status = 'void', voided_at = now(), void_reason = nullif(left(btrim(coalesce(p_reason, '')), 200), '') where id = p_id returning * into i;
  elsif p_status in ('draft', 'sent') then
    if i.status = 'paid' then raise exception 'This invoice is paid. Mark it unpaid first'; end if;
    if i.status = 'void' and not public.is_admin() then raise exception 'Only an administrator can restore a voided invoice'; end if;
    update public.invoices set status = p_status, voided_at = null, void_reason = null,
        sent_at = case when p_status = 'sent' then coalesce(sent_at, now()) else null end where id = p_id returning * into i;
  else raise exception 'That status is not valid';
  end if;
  return public.inv_json(i, false);
end $$;

create or replace function public.inv_pay(p_id uuid, p_amount numeric, p_on date, p_method text, p_ref text, p_note text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i public.invoices;
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Only an administrator can mark invoices paid'; end if;
  select * into i from public.invoices where id = p_id for update;
  if not found then raise exception 'That invoice was not found'; end if;
  if i.status = 'void' then raise exception 'A voided invoice can''t be paid'; end if;
  if p_amount is null or p_amount <= 0 or p_amount > 10000000 then raise exception 'Enter the amount that was paid'; end if;
  if p_on is null or p_on > public.inv_today() then raise exception 'Pick the day it was paid (not in the future)'; end if;
  if length(coalesce(p_method, '')) > 40 or length(coalesce(p_ref, '')) > 80 or length(coalesce(p_note, '')) > 400 then raise exception 'Some of the payment details are too long'; end if;
  update public.invoices set status = 'paid', sent_at = coalesce(sent_at, now()), paid_amount = round(p_amount, 2), paid_on = p_on,
      paid_method = nullif(btrim(coalesce(p_method, '')), ''), paid_ref = nullif(btrim(coalesce(p_ref, '')), ''),
      paid_note = nullif(btrim(coalesce(p_note, '')), ''), paid_by = auth.uid()
  where id = p_id returning * into i;
  return public.inv_json(i, false);
end $$;

create or replace function public.inv_unpay(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i public.invoices;
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Only an administrator can change a payment'; end if;
  update public.invoices set status = 'sent', paid_amount = null, paid_on = null, paid_method = null, paid_ref = null, paid_note = null, paid_by = null
  where id = p_id and status = 'paid' returning * into i;
  if not found then raise exception 'That invoice is not marked paid'; end if;
  return public.inv_json(i, false);
end $$;

-- Only drafts can be removed (the audit log keeps a copy). Issued invoices are voided instead.
create or replace function public.inv_delete(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i public.invoices;
begin
  select * into i from public.invoices where id = p_id for update;
  if not found or not public.inv_mine(i) then raise exception 'That invoice was not found'; end if;
  if i.status <> 'draft' then raise exception 'Only drafts can be deleted. Void an issued invoice instead'; end if;
  delete from public.invoices where id = p_id;
  return jsonb_build_object('ok', true);
end $$;

-- Client suggestions for the invoice form: past invoices you can see, deals and leads matching what you type.
create or replace function public.inv_clients(p_q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare q text := btrim(coalesce(p_q, '')); pat text;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if length(q) > 80 then q := left(q, 80); end if;
  pat := '%' || replace(replace(replace(q, '\', '\\'), '%', '\%'), '_', '\_') || '%';
  return coalesce((select jsonb_agg(x) from (
    select * from (
      select distinct on (lower(i.client_name)) 'invoice' as source, i.client_name as name, i.client_contact as contact, i.client_email as email,
             i.client_phone as phone, i.client_address as address, i.lead_id, i.deal_id, i.created_at as at
      from public.invoices i where public.inv_mine(i) and i.client_name ilike pat
      order by lower(i.client_name), i.created_at desc) a
    union all
    select * from (
      select 'deal', d.client, coalesce(nullif(l.owner_name, 'N/A'), ''), coalesce(nullif(l.email, 'N/A'), ''), coalesce(l.phone, ''),
             coalesce(nullif(l.address, 'N/A'), ''), d.lead_id, d.id, d.created_at
      from public.deals d left join public.leads l on l.id = d.lead_id
      where d.client ilike pat order by d.created_at desc limit 15) b
    union all
    select * from (
      select 'lead', l.name, coalesce(nullif(l.owner_name, 'N/A'), ''), coalesce(nullif(l.email, 'N/A'), ''), l.phone,
             coalesce(nullif(l.address, 'N/A'), ''), l.id, null::uuid, l.updated_at
      from public.leads l where q <> '' and l.name ilike pat order by (l.status <> 'none') desc, l.updated_at desc limit 15) c
    limit 40) x), '[]'::jsonb);
end $$;

-- ---------------------------------------------------------------- template functions
create or replace function public.inv_tpl_list() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', t.id, 'name', t.name, 'category', t.category, 'summary', t.summary, 'items', t.items,
           'payment_terms', t.payment_terms, 'notes', t.notes, 'terms', t.terms, 'due_days', t.due_days, 'tax_rate', t.tax_rate,
           'source', t.source, 'archived', t.archived, 'sort', t.sort, 'updated_at', t.updated_at, 'version', t.version)
         order by t.archived, t.sort, t.name), '[]'::jsonb)
  from public.invoice_templates t
$$;

create or replace function public.inv_tpl_save(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare t public.invoice_templates; nm text := btrim(coalesce(p->>'name', '')); it jsonb; dd integer; tr numeric;
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Only an administrator can change invoice templates'; end if;
  if p is null or jsonb_typeof(p) <> 'object' then raise exception 'Nothing to save'; end if;
  if nm = '' or length(nm) > 80 then raise exception 'Give the template a name (up to 80 characters)'; end if;
  it := public.inv_items(coalesce(p->'items', '[]'::jsonb));
  begin
    dd := coalesce(nullif(p->>'due_days', '')::int, 14);
    tr := nullif(p->>'tax_rate', '')::numeric;
  exception when others then raise exception 'Check the days to pay and the tax rate';
  end;
  if dd < 0 or dd > 365 then raise exception 'Days to pay must be between 0 and 365'; end if;
  if tr is not null and (tr < 0 or tr > 30) then raise exception 'The tax rate must be between 0 and 30 percent'; end if;
  if length(coalesce(p->>'category', '')) > 60 or length(coalesce(p->>'summary', '')) > 300 or length(coalesce(p->>'source', '')) > 200
     or length(coalesce(p->>'payment_terms', '')) > 2000 or length(coalesce(p->>'notes', '')) > 4000 or length(coalesce(p->>'terms', '')) > 20000
     then raise exception 'Some of the template text is too long'; end if;
  if nullif(p->>'id', '') is null then
    insert into public.invoice_templates (name, category, summary, items, payment_terms, notes, terms, due_days, tax_rate, source, sort)
    values (nm, btrim(coalesce(p->>'category', '')), btrim(coalesce(p->>'summary', '')), it, coalesce(p->>'payment_terms', ''),
            coalesce(p->>'notes', ''), coalesce(p->>'terms', ''), dd, tr, btrim(coalesce(p->>'source', '')), coalesce(nullif(p->>'sort', '')::int, 0))
    returning * into t;
  else
    update public.invoice_templates set name = nm, category = btrim(coalesce(p->>'category', '')), summary = btrim(coalesce(p->>'summary', '')),
        items = it, payment_terms = coalesce(p->>'payment_terms', ''), notes = coalesce(p->>'notes', ''), terms = coalesce(p->>'terms', ''),
        due_days = dd, tax_rate = tr, source = btrim(coalesce(p->>'source', '')), sort = coalesce(nullif(p->>'sort', '')::int, sort)
    where id = (p->>'id')::uuid returning * into t;
    if not found then raise exception 'That template was not found'; end if;
  end if;
  return jsonb_build_object('id', t.id, 'version', t.version);
end $$;

create or replace function public.inv_tpl_archive(p_id uuid, p_archived boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Only an administrator can change invoice templates'; end if;
  update public.invoice_templates set archived = coalesce(p_archived, true) where id = p_id;
  if not found then raise exception 'That template was not found'; end if;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- permissions
do $$
declare f text;
begin
  foreach f in array array[
    'public.team_cards()', 'public.team_card_set(uuid, text, text, text, text, text)',
    'public.inv_settings()', 'public.inv_settings_set(jsonb)', 'public.inv_list()', 'public.inv_get(uuid)', 'public.inv_save(jsonb)',
    'public.inv_duplicate(uuid)', 'public.inv_set_status(uuid, text, text)', 'public.inv_pay(uuid, numeric, date, text, text, text)',
    'public.inv_unpay(uuid)', 'public.inv_delete(uuid)', 'public.inv_clients(text)', 'public.inv_tpl_list()', 'public.inv_tpl_save(jsonb)',
    'public.inv_tpl_archive(uuid, boolean)'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated', f);
  end loop;
  foreach f in array array['public.inv_next_number()', 'public.inv_items(jsonb)', 'public.inv_totals(jsonb, text, numeric, numeric)', 'public.inv_today()'] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
  end loop;
end $$;
