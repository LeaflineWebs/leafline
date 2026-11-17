-- Leafline 11.20: the email writer (18th database update). Safe to run more than once. Nothing existing is changed or removed
-- (team_health() is replaced so it also reports this update).
--   * The emails themselves are written by the Supabase Edge Function "email-draft", which holds the AI key as a secret.
--     The app never sees that key.
--   * email_quota_take(): the function calls this AS THE PERSON WHO ASKED (their own sign-in), before every email. It checks
--     they are signed in and active, and keeps each person to EMAIL_DAILY_LIMIT emails in 24 hours (so a lost laptop or a
--     loop can't run up the AI bill). Only the time and the business id are kept, never the email itself, for 30 days.

-- ---------------------------------------------------------------- usage log
create table if not exists public.email_drafts (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references public.profiles(id) on delete cascade,
  lead_id     text not null default '' check (length(lead_id) <= 80),
  created_at  timestamptz not null default now()
);
create index if not exists email_drafts_user_idx on public.email_drafts (user_id, created_at desc);
alter table public.email_drafts enable row level security;
drop policy if exists email_drafts_read on public.email_drafts;
create policy email_drafts_read on public.email_drafts for select to authenticated
  using (public.is_active() and (user_id = auth.uid() or public.is_admin()));
-- no insert/update/delete policies: rows are only added by email_quota_take()

create or replace function public.email_quota_take(p_lead text default '') returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); n integer; lim constant integer := 150;   -- EMAIL_DAILY_LIMIT
begin
  if me is null or not public.is_active() then
    return jsonb_build_object('ok', false, 'error', 'Sign in first.');
  end if;
  perform pg_advisory_xact_lock(hashtext('email_quota:' || me::text));   -- two clicks at once can't both slip past the limit
  delete from public.email_drafts where user_id = me and created_at < now() - interval '30 days';
  select count(*) into n from public.email_drafts where user_id = me and created_at > now() - interval '24 hours';
  if n >= lim then
    return jsonb_build_object('ok', false, 'limit_reached', true, 'used', n, 'limit', lim,
      'error', 'You''ve written ' || lim || ' emails in the last 24 hours, the most allowed. Try again later.');
  end if;
  insert into public.email_drafts (user_id, lead_id) values (me, left(coalesce(p_lead, ''), 80));
  return jsonb_build_object('ok', true, 'used', n + 1, 'limit', lim);
end $$;
revoke all on function public.email_quota_take(text) from public;
grant execute on function public.email_quota_take(text) to authenticated;

-- ---------------------------------------------------------------- System health also reports update 18
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
    '18', true);
  return jsonb_build_object('updates', u, 'checked_at', now(), 'people', coalesce((
    select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'username', p.username, 'role', p.role, 'active', p.active,
                                        'last_seen', p.last_seen, 'version', s.version, 'platform', s.platform, 'sync_state', s.sync_state,
                                        'pending', s.pending, 'last_error', s.last_error, 'reported_at', s.updated_at)
                     order by p.active desc, p.display_name)
    from public.profiles p left join public.app_status s on s.user_id = p.id), '[]'::jsonb));
end $$;
revoke all on function public.team_health() from public;
grant execute on function public.team_health() to authenticated;
