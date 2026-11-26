-- Leafline 12.0.1 - 20th database update: a fingerprint of each person's profile picture.
-- Pictures are stored inside profiles (up to 60 KB each). Re-downloading everyone's picture every minute used up the
-- free plan's monthly download allowance. With this column the app downloads only a tiny fingerprint (32 characters)
-- and fetches a picture again only when that person actually changed it. Until it is run, the app refreshes
-- pictures every 30 minutes instead.
-- Safe to run more than once. Adds one computed column (the database fills it in itself); nothing existing changes.

alter table public.profiles add column if not exists avatar_sig text generated always as (md5(coalesce(avatar, ''))) stored;

-- ---------------------------------------------------------------- health check reports update 20
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
    '18', to_regclass('public.email_drafts') is not null,
    '19', to_regclass('public.clients') is not null,
    '20', true);
  return jsonb_build_object('updates', u, 'checked_at', now(), 'people', coalesce((
    select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'username', p.username, 'role', p.role, 'active', p.active,
                                        'last_seen', p.last_seen, 'version', s.version, 'platform', s.platform, 'sync_state', s.sync_state,
                                        'pending', s.pending, 'last_error', s.last_error, 'reported_at', s.updated_at)
                     order by p.active desc, p.display_name)
    from public.profiles p left join public.app_status s on s.user_id = p.id), '[]'::jsonb));
end $$;
revoke all on function public.team_health() from public;
grant execute on function public.team_health() to authenticated;
