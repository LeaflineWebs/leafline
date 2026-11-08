-- LEAFLINE: ALL DATABASE UPDATES (2 to 6) IN ONE FILE
-- Open this file in Notepad, press Ctrl+A then Ctrl+C, paste into Supabase > SQL Editor > New query, press Run.
-- Safe to run more than once. Nothing is deleted.

-- =================== 20261106000002_tasks.sql ===================
-- OPTIONAL second migration: lets calendar events be ticked off ("tasks completed" on the Team page).
-- The app works without it; ticks stay on that computer until this has been run, then upload by themselves.
alter table public.events add column if not exists done boolean not null default false;
alter table public.events add column if not exists done_at timestamptz;
alter table public.events add column if not exists done_by uuid references public.profiles(id);
create index if not exists events_done_idx on public.events (done_at) where done;

create or replace function public.stamp_done() returns trigger language plpgsql set search_path = '' as $$
begin
  if new.done and (tg_op = 'INSERT' or not old.done) then
    new.done_by := coalesce(auth.uid(), new.done_by);      -- always the person who actually ticked it
    new.done_at := coalesce(new.done_at, now());
  elsif not new.done then
    new.done_by := null; new.done_at := null;
  end if;
  return new;
end $$;
drop trigger if exists stamp_done on public.events;
create trigger stamp_done before insert or update on public.events for each row execute function public.stamp_done();

-- =================== 20261106000003_avatars.sql ===================
-- OPTIONAL third migration: profile pictures that the whole team can see (Team page).
-- Pictures are stored as small (about 192x192) images inside the profile row; no extra storage service is needed.
alter table public.profiles add column if not exists avatar text
  check (avatar is null or (length(avatar) < 60000 and avatar ~ '^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$'));

-- =================== 20261107000004_profile_extras.sql ===================
-- OPTIONAL fourth migration: richer profiles that the whole team can see
-- (job title, bio, mood, accent colour, thought of the day, banner picture).
-- Safe to run more than once. Until it is run, the app keeps these on each computer and everything else keeps working.
alter table public.profiles add column if not exists title text check (title is null or length(title) <= 40);
alter table public.profiles add column if not exists bio text check (bio is null or length(bio) <= 280);
alter table public.profiles add column if not exists mood text check (mood is null or length(mood) <= 8);
alter table public.profiles add column if not exists accent text check (accent is null or accent ~ '^#[0-9A-Fa-f]{6}$');
alter table public.profiles add column if not exists thought text check (thought is null or length(thought) <= 140);
alter table public.profiles add column if not exists thought_at timestamptz;
alter table public.profiles add column if not exists banner text
  check (banner is null or (length(banner) < 150000 and banner ~ '^data:image/(jpeg|png|webp);base64,'));
-- (No new policies are needed: the existing "update own profile" policy and the guard trigger already cover these columns.)

-- =================== 20261107000005_board_posts_media.sql ===================
-- OPTIONAL fifth migration (Leafline 11): announcements & ideas board, animated profile pictures/banners
-- (GIF, WebP, PNG, JPEG, AVIF) kept in free Supabase Storage, and a guard so leaderboard money can't be faked.
-- Safe to run more than once. Until it is run, the app keeps working: the Announcements page explains what to do,
-- and pictures fall back to the small still images from migration 3/4.

-- ---------------------------------------------------------------- announcements & ideas
create table if not exists public.posts (
  id uuid primary key default gen_random_uuid(),
  kind text not null default 'announcement' check (kind in ('announcement','idea','update')),
  title text not null check (length(btrim(title)) between 1 and 120),
  body text not null default '' check (length(body) <= 4000),
  pinned boolean not null default false,
  author_id uuid not null references public.profiles(id) default auth.uid(),
  edited_by uuid references public.profiles(id),
  edited_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists posts_created_idx on public.posts (created_at desc);

create table if not exists public.post_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.posts(id) on delete cascade,
  author_id uuid not null references public.profiles(id) default auth.uid(),
  body text not null check (length(btrim(body)) between 1 and 1000),
  created_at timestamptz not null default now()
);
create index if not exists post_comments_post_idx on public.post_comments (post_id, created_at);

create table if not exists public.post_reactions (
  post_id uuid not null references public.posts(id) on delete cascade,
  user_id uuid not null references public.profiles(id) default auth.uid(),
  emoji text not null check (emoji in ('👍','🔥','💡','🎉','❤️')),
  created_at timestamptz not null default now(),
  primary key (post_id, user_id, emoji)
);

-- Everyone on the team may edit any post (business rule chosen by the owner), but the author and the
-- creation time can never be rewritten, and every edit records who made it.
create or replace function public.guard_post() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  new.id := old.id; new.author_id := old.author_id; new.created_at := old.created_at;
  if new.title is distinct from old.title or new.body is distinct from old.body or new.kind is distinct from old.kind then
    new.edited_by := auth.uid(); new.edited_at := now();
  else
    new.edited_by := old.edited_by; new.edited_at := old.edited_at;
  end if;
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists guard_post on public.posts;
create trigger guard_post before update on public.posts for each row execute function public.guard_post();

alter table public.posts enable row level security;
alter table public.post_comments enable row level security;
alter table public.post_reactions enable row level security;
drop policy if exists posts_read on public.posts;
drop policy if exists posts_insert on public.posts;
drop policy if exists posts_update on public.posts;
drop policy if exists posts_delete on public.posts;
create policy posts_read on public.posts for select to authenticated using (public.is_active());
create policy posts_insert on public.posts for insert to authenticated with check (public.is_active() and author_id = auth.uid());
create policy posts_update on public.posts for update to authenticated using (public.is_active()) with check (public.is_active());
create policy posts_delete on public.posts for delete to authenticated using (public.is_active());
drop policy if exists pc_read on public.post_comments;
drop policy if exists pc_insert on public.post_comments;
drop policy if exists pc_update on public.post_comments;
drop policy if exists pc_delete on public.post_comments;
create policy pc_read on public.post_comments for select to authenticated using (public.is_active());
create policy pc_insert on public.post_comments for insert to authenticated with check (public.is_active() and author_id = auth.uid());
create policy pc_update on public.post_comments for update to authenticated using (public.is_active()) with check (public.is_active());
create policy pc_delete on public.post_comments for delete to authenticated using (public.is_active());
drop policy if exists pr_read on public.post_reactions;
drop policy if exists pr_insert on public.post_reactions;
drop policy if exists pr_delete on public.post_reactions;
create policy pr_read on public.post_reactions for select to authenticated using (public.is_active());
create policy pr_insert on public.post_reactions for insert to authenticated with check (public.is_active() and user_id = auth.uid());
create policy pr_delete on public.post_reactions for delete to authenticated using (public.is_active() and user_id = auth.uid());

-- ---------------------------------------------------------------- leaderboard integrity
-- Money on the leaderboard = payments collected on deals each person owns. Only an admin may give a deal
-- to someone else or move it between people; everyone else can only own their own deals.
create or replace function public.guard_deal_owner() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or public.is_admin() then return new; end if;
  if tg_op = 'INSERT' then
    if new.owner_id is not null and new.owner_id <> auth.uid() then raise exception 'You can only add deals for yourself'; end if;
    new.owner_id := coalesce(new.owner_id, auth.uid());
  elsif new.owner_id is distinct from old.owner_id then
    raise exception 'Only an administrator can change who owns a deal';
  end if;
  return new;
end $$;
drop trigger if exists guard_deal_owner on public.deals;
create trigger guard_deal_owner before insert or update on public.deals for each row execute function public.guard_deal_owner();

-- ---------------------------------------------------------------- animated pictures & banners
alter table public.profiles add column if not exists avatar_url text
  check (avatar_url is null or avatar_url ~ '^https://[A-Za-z0-9.-]+(:[0-9]+)?/storage/v1/object/public/media/[0-9a-f-]{36}/[A-Za-z0-9._-]{1,80}$');
alter table public.profiles add column if not exists banner_url text
  check (banner_url is null or banner_url ~ '^https://[A-Za-z0-9.-]+(:[0-9]+)?/storage/v1/object/public/media/[0-9a-f-]{36}/[A-Za-z0-9._-]{1,80}$');
alter table public.profiles add column if not exists banner_pos smallint check (banner_pos is null or banner_pos between 0 and 100);

-- A public bucket: pictures load fast from the CDN and are cached. File names are random, max 8 MB each,
-- images only (no SVG, so no scripts). Supabase's free plan includes 1 GB of storage.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('media', 'media', true, 8388608, array['image/gif','image/webp','image/png','image/jpeg','image/avif'])
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists media_insert on storage.objects;
drop policy if exists media_update on storage.objects;
drop policy if exists media_delete on storage.objects;
drop policy if exists media_select on storage.objects;
-- each person can only write inside their own folder:  media/<their user id>/...
create policy media_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text and public.is_active());
create policy media_update on storage.objects for update to authenticated
  using (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text);
create policy media_delete on storage.objects for delete to authenticated
  using (bucket_id = 'media' and ((storage.foldername(name))[1] = auth.uid()::text or public.is_admin()));
create policy media_select on storage.objects for select to authenticated
  using (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text);

-- =================== 20261107000006_credit.sql ===================
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
