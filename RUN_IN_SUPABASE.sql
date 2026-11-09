-- LEAFLINE: ALL DATABASE UPDATES (2 to 13) IN ONE FILE
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

-- =================== 20261108000007_confirm_payments.sql ===================
-- Seventh migration (Leafline 11.3): "Confirm payment". Safe to run more than once.
-- A deal payment now counts toward the money made only after someone ticks it as really received.
-- The ticks are stored on the deal as a comma-separated list of "YYYY-MM-DD:upfront" / "YYYY-MM-DD:monthly" keys.
-- Until this is run, ticks stay on the computer that made them and upload by themselves afterwards.
alter table public.deals add column if not exists confirmed text not null default '';
do $$ begin
  alter table public.deals add constraint deals_confirmed_shape
    check (length(confirmed) < 20000 and confirmed ~ '^([0-9]{4}-[0-9]{2}-[0-9]{2}:(upfront|monthly)(,|$))*$');
exception when duplicate_object then null; end $$;

-- =================== 20261108000008_messaging.sql ===================
-- Eighth migration (Leafline 11.4): team Messages (direct chats, group chats, mentions, reactions, replies,
-- pins, files, read receipts, typing, notifications, search). Safe to run more than once. Nothing is deleted.
--
-- Security model
--   * Every table below has row level security. People can only READ rows of conversations they belong to.
--   * Nobody writes to these tables directly. Every change goes through a msg_* function that checks who is
--     calling (auth.uid()), that they are an active teammate, and that they belong to the conversation.
--     The sender of a message is always the caller: it can never be chosen by the client.
--   * Files live in the PRIVATE bucket "message-files" under <conversation id>/<uploader id>/<file>. Only members
--     of that conversation can upload into it or read from it; links handed out are short-lived signed URLs.
--   * Reads go through SECURITY INVOKER functions, so the same row level security applies to them too.

-- ---------------------------------------------------------------- tables
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('direct', 'group')),
  name text not null default '' check (length(name) <= 80),
  description text not null default '' check (length(description) <= 500),
  avatar_url text check (avatar_url is null or (length(avatar_url) < 1000 and avatar_url ~ '^https://[^\s"''<>]+$')),
  direct_key text unique,                                   -- "<smaller id>:<larger id>": one direct chat per pair
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_message_at timestamptz not null default now(),
  check ((type = 'direct') = (direct_key is not null))
);
create index if not exists conversations_last_idx on public.conversations (last_message_at desc);

create table if not exists public.conversation_members (
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member')),
  joined_at timestamptz not null default now(),
  last_read_at timestamptz not null default now(),
  is_muted boolean not null default false,
  is_pinned boolean not null default false,
  is_archived boolean not null default false,
  typing_at timestamptz,
  primary key (conversation_id, user_id)
);
create index if not exists conversation_members_user_idx on public.conversation_members (user_id);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  sender_id uuid references public.profiles(id) on delete set null,
  client_op_id uuid unique,                                 -- a retried send can never create a second copy
  content text not null default '' check (length(content) <= 8000),
  message_type text not null default 'text' check (message_type in ('text', 'system')),
  meta jsonb not null default '{}'::jsonb,                  -- system messages: {"action": "added", "users": [...]}
  reply_to_message_id uuid references public.messages(id) on delete set null,
  mentions_everyone boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  edited_at timestamptz,
  deleted_at timestamptz,
  deleted_by uuid references public.profiles(id) on delete set null
);
create index if not exists messages_conv_time_idx on public.messages (conversation_id, created_at desc, id desc);
create index if not exists messages_sender_idx on public.messages (sender_id, created_at desc);

create table if not exists public.message_mentions (
  message_id uuid not null references public.messages(id) on delete cascade,
  mentioned_user_id uuid not null references public.profiles(id) on delete cascade,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (message_id, mentioned_user_id)
);
create index if not exists message_mentions_user_idx on public.message_mentions (mentioned_user_id, created_at desc);

create table if not exists public.message_reactions (
  message_id uuid not null references public.messages(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  emoji text not null check (length(emoji) between 1 and 16 and emoji !~ '\s'),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (message_id, user_id, emoji)
);
create index if not exists message_reactions_conv_idx on public.message_reactions (conversation_id);

create table if not exists public.message_attachments (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.messages(id) on delete cascade,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  file_name text not null check (length(file_name) between 1 and 200),
  file_path text not null unique check (length(file_path) < 400),
  file_type text not null default '' check (length(file_type) <= 120),
  file_size bigint not null check (file_size between 0 and 26214400),
  uploaded_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists message_attachments_conv_idx on public.message_attachments (conversation_id, created_at desc);
create index if not exists message_attachments_msg_idx on public.message_attachments (message_id);

create table if not exists public.message_notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  message_id uuid references public.messages(id) on delete cascade,
  actor_id uuid references public.profiles(id) on delete set null,
  notification_type text not null check (notification_type in ('direct', 'mention', 'everyone', 'reply', 'member')),
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists message_notifications_user_idx on public.message_notifications (user_id, is_read, created_at desc);

create table if not exists public.pinned_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  message_id uuid not null unique references public.messages(id) on delete cascade,
  pinned_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists pinned_messages_conv_idx on public.pinned_messages (conversation_id, created_at desc);

-- ---------------------------------------------------------------- helpers
create or replace function public.msg_uuid(t text) returns uuid
language plpgsql immutable set search_path = '' as $$
begin return t::uuid; exception when others then return null; end $$;

create or replace function public.msg_is_member(c uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_active() and exists (
    select 1 from public.conversation_members m where m.conversation_id = c and m.user_id = auth.uid())
$$;

create or replace function public.msg_role(c uuid) returns text
language sql stable security definer set search_path = '' as $$
  select m.role from public.conversation_members m where m.conversation_id = c and m.user_id = auth.uid()
$$;

-- a file can be read while the message holding it still exists (checked with full visibility, so deleted messages count)
create or replace function public.msg_file_open(p_name text) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.msg_is_member(public.msg_uuid((storage.foldername(p_name))[1]))
     and not exists (select 1 from public.message_attachments a join public.messages m on m.id = a.message_id
                     where a.file_path = p_name and m.deleted_at is not null)
$$;

-- names for system messages and notifications
create or replace function public.msg_name(u uuid) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select p.display_name from public.profiles p where p.id = u), 'Someone')
$$;

create or replace function public.msg_require_member(c uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first' using errcode = '42501'; end if;
  if not public.msg_is_member(c) then raise exception 'You are not in this conversation' using errcode = '42501'; end if;
end $$;

create or replace function public.msg_system(c uuid, action text, users uuid[], extra jsonb default '{}'::jsonb) returns uuid
language plpgsql security definer set search_path = '' as $$
declare mid uuid;
begin
  insert into public.messages (conversation_id, sender_id, message_type, meta)
  values (c, auth.uid(), 'system', jsonb_build_object('action', action, 'users', to_jsonb(coalesce(users, '{}'::uuid[]))) || extra)
  returning id into mid;
  update public.conversations set last_message_at = now(), updated_at = now() where id = c;
  return mid;
end $$;

-- ---------------------------------------------------------------- row level security (read only; writes go through msg_* functions)
alter table public.conversations enable row level security;
alter table public.conversation_members enable row level security;
alter table public.messages enable row level security;
alter table public.message_mentions enable row level security;
alter table public.message_reactions enable row level security;
alter table public.message_attachments enable row level security;
alter table public.message_notifications enable row level security;
alter table public.pinned_messages enable row level security;

drop policy if exists conversations_read on public.conversations;
create policy conversations_read on public.conversations for select to authenticated using (public.msg_is_member(id));
drop policy if exists conversation_members_read on public.conversation_members;
create policy conversation_members_read on public.conversation_members for select to authenticated using (public.msg_is_member(conversation_id));
drop policy if exists messages_read on public.messages;
create policy messages_read on public.messages for select to authenticated using (public.msg_is_member(conversation_id));
drop policy if exists message_mentions_read on public.message_mentions;
create policy message_mentions_read on public.message_mentions for select to authenticated using (public.msg_is_member(conversation_id));
drop policy if exists message_reactions_read on public.message_reactions;
create policy message_reactions_read on public.message_reactions for select to authenticated using (public.msg_is_member(conversation_id));
drop policy if exists message_attachments_read on public.message_attachments;
create policy message_attachments_read on public.message_attachments for select to authenticated
  using (public.msg_is_member(conversation_id) and exists (select 1 from public.messages m where m.id = message_id and m.deleted_at is null));
drop policy if exists pinned_messages_read on public.pinned_messages;
create policy pinned_messages_read on public.pinned_messages for select to authenticated using (public.msg_is_member(conversation_id));
drop policy if exists message_notifications_read on public.message_notifications;
create policy message_notifications_read on public.message_notifications for select to authenticated using (user_id = auth.uid());
drop policy if exists message_notifications_mark on public.message_notifications;
create policy message_notifications_mark on public.message_notifications for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- no direct writes at all, belt and braces on top of "no policy = no access"
revoke insert, update, delete on public.conversations, public.conversation_members, public.messages, public.message_mentions,
  public.message_reactions, public.message_attachments, public.pinned_messages from anon, authenticated;
revoke insert, update, delete on public.message_notifications from anon, authenticated;
grant update (is_read) on public.message_notifications to authenticated;
revoke all on public.conversations, public.conversation_members, public.messages, public.message_mentions,
  public.message_reactions, public.message_attachments, public.pinned_messages, public.message_notifications from anon;
grant select on public.conversations, public.conversation_members, public.messages, public.message_mentions,
  public.message_reactions, public.message_attachments, public.pinned_messages, public.message_notifications to authenticated;

-- ---------------------------------------------------------------- conversations
create or replace function public.msg_start_direct(p_other uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); k text; cid uuid;
begin
  if me is null or not public.is_active() then raise exception 'Sign in first' using errcode = '42501'; end if;
  if p_other is null or p_other = me then raise exception 'Pick a teammate'; end if;
  if not exists (select 1 from public.profiles p where p.id = p_other and p.active) then raise exception 'That teammate is not active'; end if;
  k := least(me::text, p_other::text) || ':' || greatest(me::text, p_other::text);
  select id into cid from public.conversations where direct_key = k;
  if cid is null then
    insert into public.conversations (type, direct_key, created_by) values ('direct', k, me)
    on conflict (direct_key) do nothing returning id into cid;
    if cid is null then select id into cid from public.conversations where direct_key = k; end if;
  end if;
  insert into public.conversation_members (conversation_id, user_id, role) values (cid, me, 'member'), (cid, p_other, 'member')
  on conflict do nothing;
  update public.conversation_members set is_archived = false where conversation_id = cid and user_id = me;
  return cid;
end $$;

create or replace function public.msg_create_group(p_name text, p_description text, p_members uuid[]) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); cid uuid; nm text := btrim(coalesce(p_name, '')); added uuid[];
begin
  if me is null or not public.is_active() then raise exception 'Sign in first' using errcode = '42501'; end if;
  if nm = '' then raise exception 'Give the group a name'; end if;
  if length(nm) > 80 then raise exception 'Group names can be up to 80 characters'; end if;
  insert into public.conversations (type, name, description, created_by)
  values ('group', nm, left(btrim(coalesce(p_description, '')), 500), me) returning id into cid;
  insert into public.conversation_members (conversation_id, user_id, role) values (cid, me, 'owner');
  select coalesce(array_agg(p.id), '{}') into added from public.profiles p
    where p.id = any (coalesce(p_members, '{}')) and p.active and p.id <> me;
  insert into public.conversation_members (conversation_id, user_id) select cid, u from unnest(added) u on conflict do nothing;
  perform public.msg_system(cid, 'created', added, jsonb_build_object('name', nm));
  insert into public.message_notifications (user_id, conversation_id, actor_id, notification_type)
    select u, cid, me, 'member' from unnest(added) u;
  return cid;
end $$;

create or replace function public.msg_update_group(p_conv uuid, p_name text default null, p_description text default null, p_avatar_url text default null)
returns void language plpgsql security definer set search_path = '' as $$
declare c public.conversations; nm text;
begin
  perform public.msg_require_member(p_conv);
  select * into c from public.conversations where id = p_conv;
  if c.type <> 'group' then raise exception 'Only group chats have a name and picture'; end if;
  if p_name is not null then
    nm := btrim(p_name);
    if nm = '' then raise exception 'Give the group a name'; end if;
    if length(nm) > 80 then raise exception 'Group names can be up to 80 characters'; end if;
    if nm <> c.name then
      update public.conversations set name = nm, updated_at = now() where id = p_conv;
      perform public.msg_system(p_conv, 'renamed', '{}', jsonb_build_object('name', nm, 'old', c.name));
    end if;
  end if;
  if p_description is not null then
    update public.conversations set description = left(btrim(p_description), 500), updated_at = now() where id = p_conv;
  end if;
  if p_avatar_url is not null then
    if p_avatar_url <> '' and (length(p_avatar_url) >= 1000 or p_avatar_url !~ '^https://[^\s"''<>]+$') then raise exception 'That picture link is not allowed'; end if;
    update public.conversations set avatar_url = nullif(p_avatar_url, ''), updated_at = now() where id = p_conv;
    perform public.msg_system(p_conv, 'picture', '{}');
  end if;
end $$;

create or replace function public.msg_add_members(p_conv uuid, p_users uuid[]) returns integer
language plpgsql security definer set search_path = '' as $$
declare added uuid[];
begin
  perform public.msg_require_member(p_conv);
  if (select type from public.conversations where id = p_conv) <> 'group' then raise exception 'Start a group chat to add more people'; end if;
  with ins as (
    insert into public.conversation_members (conversation_id, user_id)
    select p_conv, p.id from public.profiles p where p.id = any (coalesce(p_users, '{}')) and p.active
    on conflict do nothing returning user_id)
  select coalesce(array_agg(user_id), '{}') into added from ins;
  if cardinality(added) > 0 then
    perform public.msg_system(p_conv, 'added', added);
    insert into public.message_notifications (user_id, conversation_id, actor_id, notification_type)
      select u, p_conv, auth.uid(), 'member' from unnest(added) u;
  end if;
  return cardinality(added);
end $$;

-- p_user = yourself means "leave". Removing someone else needs group owner/admin or a Leafline admin.
create or replace function public.msg_remove_member(p_conv uuid, p_user uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); r text; nxt uuid;
begin
  perform public.msg_require_member(p_conv);
  if (select type from public.conversations where id = p_conv) <> 'group' then raise exception 'You can archive a direct chat, but not leave it'; end if;
  if not exists (select 1 from public.conversation_members where conversation_id = p_conv and user_id = p_user) then return; end if;
  if p_user <> me then
    r := public.msg_role(p_conv);
    if not (r in ('owner', 'admin') or public.is_admin()) then raise exception 'Only the group owner or an admin can remove people' using errcode = '42501'; end if;
    if (select role from public.conversation_members where conversation_id = p_conv and user_id = p_user) = 'owner' and not public.is_admin() then
      raise exception 'The group owner can only be removed by a Leafline admin' using errcode = '42501'; end if;
  end if;
  perform public.msg_system(p_conv, case when p_user = me then 'left' else 'removed' end, array[p_user]);
  delete from public.conversation_members where conversation_id = p_conv and user_id = p_user;
  delete from public.message_notifications where conversation_id = p_conv and user_id = p_user;
  -- the group keeps an owner: the longest-standing member takes over
  if not exists (select 1 from public.conversation_members where conversation_id = p_conv and role = 'owner') then
    select user_id into nxt from public.conversation_members where conversation_id = p_conv order by joined_at, user_id limit 1;
    if nxt is not null then update public.conversation_members set role = 'owner' where conversation_id = p_conv and user_id = nxt; end if;
  end if;
end $$;

create or replace function public.msg_set_prefs(p_conv uuid, p_muted boolean default null, p_pinned boolean default null, p_archived boolean default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform public.msg_require_member(p_conv);
  update public.conversation_members set is_muted = coalesce(p_muted, is_muted), is_pinned = coalesce(p_pinned, is_pinned),
    is_archived = coalesce(p_archived, is_archived) where conversation_id = p_conv and user_id = auth.uid();
end $$;

create or replace function public.msg_typing(p_conv uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.msg_require_member(p_conv);
  update public.conversation_members set typing_at = now() where conversation_id = p_conv and user_id = auth.uid()
    and (typing_at is null or typing_at < now() - interval '2 seconds');
end $$;

create or replace function public.msg_mark_read(p_conv uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.msg_require_member(p_conv);
  update public.conversation_members set last_read_at = greatest(last_read_at, now()), typing_at = null
    where conversation_id = p_conv and user_id = auth.uid();
  update public.message_notifications set is_read = true where user_id = auth.uid() and conversation_id = p_conv and not is_read;
end $$;

create or replace function public.msg_mark_all_read() returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Sign in first' using errcode = '42501'; end if;
  update public.message_notifications set is_read = true where user_id = auth.uid() and not is_read;
end $$;

-- ---------------------------------------------------------------- messages
-- Mentions are stored in the text as <@user-id> / <@everyone> AND as rows in message_mentions.
create or replace function public.msg_send(p_conv uuid, p_client_op_id uuid, p_content text, p_reply_to uuid default null,
  p_mentions uuid[] default null, p_everyone boolean default false, p_attachments jsonb default '[]'::jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); c public.conversations; mid uuid; body text := coalesce(p_content, ''); ment uuid[]; att jsonb;
  reply_owner uuid; files int := 0; everyone boolean := coalesce(p_everyone, false); r text;
begin
  perform public.msg_require_member(p_conv);
  if p_client_op_id is not null then
    select id into mid from public.messages where client_op_id = p_client_op_id;
    if mid is not null then                                  -- a retry of something that already arrived
      if (select sender_id from public.messages where id = mid) <> me then raise exception 'Duplicate message id'; end if;
      return jsonb_build_object('id', mid, 'duplicate', true);
    end if;
  end if;
  if length(body) > 8000 then raise exception 'Messages can be up to 8000 characters'; end if;
  if jsonb_typeof(coalesce(p_attachments, '[]'::jsonb)) <> 'array' or jsonb_array_length(coalesce(p_attachments, '[]'::jsonb)) > 10 then
    raise exception 'Up to 10 files per message'; end if;
  files := jsonb_array_length(coalesce(p_attachments, '[]'::jsonb));
  if btrim(body) = '' and files = 0 then raise exception 'Type a message first'; end if;
  select * into c from public.conversations where id = p_conv;
  if everyone then
    r := public.msg_role(p_conv);
    if c.type <> 'group' then everyone := false;
    elsif not (r in ('owner', 'admin') or public.is_admin()) then raise exception 'Only the group owner, group admins or a Leafline admin can use @everyone' using errcode = '42501'; end if;
  end if;
  if p_reply_to is not null and not exists (select 1 from public.messages where id = p_reply_to and conversation_id = p_conv) then
    raise exception 'The message you replied to is not in this conversation'; end if;
  insert into public.messages (conversation_id, sender_id, client_op_id, content, reply_to_message_id, mentions_everyone)
  values (p_conv, me, p_client_op_id, body, p_reply_to, everyone) returning id into mid;
  -- files: only your own uploads, inside this conversation's folder
  for att in select * from jsonb_array_elements(coalesce(p_attachments, '[]'::jsonb)) loop
    if (storage.foldername(att->>'path'))[1] is distinct from p_conv::text or (storage.foldername(att->>'path'))[2] is distinct from me::text then
      raise exception 'That file was not uploaded to this conversation'; end if;
    if not exists (select 1 from storage.objects o where o.bucket_id = 'message-files' and o.name = att->>'path') then
      raise exception 'That file has not finished uploading'; end if;
    insert into public.message_attachments (message_id, conversation_id, file_name, file_path, file_type, file_size, uploaded_by)
    values (mid, p_conv, left(coalesce(nullif(btrim(att->>'name'), ''), 'file'), 200), att->>'path', left(coalesce(att->>'type', ''), 120),
            greatest(0, least(26214400, coalesce((att->>'size')::bigint, 0))), me);
  end loop;
  -- mentions: only people in this conversation (never reveals the chat to anyone else)
  select coalesce(array_agg(distinct m.user_id), '{}') into ment from public.conversation_members m
    where m.conversation_id = p_conv and m.user_id = any (coalesce(p_mentions, '{}')) and m.user_id <> me;
  insert into public.message_mentions (message_id, mentioned_user_id, conversation_id) select mid, u, p_conv from unnest(ment) u;
  update public.conversations set last_message_at = now(), updated_at = now() where id = p_conv;
  update public.conversation_members set last_read_at = greatest(last_read_at, now()), typing_at = null, is_archived = false
    where conversation_id = p_conv and user_id = me;
  update public.conversation_members set is_archived = false where conversation_id = p_conv and is_archived and not is_muted;
  -- notifications: never for your own message; muted chats only notify direct mentions
  select sender_id into reply_owner from public.messages where id = p_reply_to;
  insert into public.message_notifications (user_id, conversation_id, message_id, actor_id, notification_type)
  select m.user_id, p_conv, mid, me,
         case when m.user_id = any (ment) then 'mention'
              when everyone then 'everyone'
              when m.user_id = reply_owner then 'reply'
              else 'direct' end
  from public.conversation_members m
  where m.conversation_id = p_conv and m.user_id <> me
    and (m.user_id = any (ment)
         or (not m.is_muted and (everyone or m.user_id = reply_owner or c.type = 'direct')));
  return jsonb_build_object('id', mid, 'duplicate', false);
end $$;

create or replace function public.msg_edit(p_id uuid, p_content text, p_mentions uuid[] default null, p_everyone boolean default null)
returns void language plpgsql security definer set search_path = '' as $$
declare m public.messages; ment uuid[]; c text;
begin
  select * into m from public.messages where id = p_id;
  if m.id is null then raise exception 'Message not found'; end if;
  perform public.msg_require_member(m.conversation_id);
  if m.sender_id is distinct from auth.uid() then raise exception 'You can only edit your own messages' using errcode = '42501'; end if;
  if m.deleted_at is not null or m.message_type <> 'text' then raise exception 'This message can''t be edited'; end if;
  if btrim(coalesce(p_content, '')) = '' and not exists (select 1 from public.message_attachments where message_id = p_id) then
    raise exception 'Type a message first'; end if;
  if length(p_content) > 8000 then raise exception 'Messages can be up to 8000 characters'; end if;
  update public.messages set content = p_content, edited_at = now(), updated_at = now(),
    mentions_everyone = case when p_everyone is null then mentions_everyone else mentions_everyone and p_everyone end
    where id = p_id;
  select coalesce(array_agg(distinct cm.user_id), '{}') into ment from public.conversation_members cm
    where cm.conversation_id = m.conversation_id and cm.user_id = any (coalesce(p_mentions, '{}')) and cm.user_id <> auth.uid();
  -- newly mentioned people get a notification; people no longer mentioned lose the mention
  insert into public.message_notifications (user_id, conversation_id, message_id, actor_id, notification_type)
    select u, m.conversation_id, p_id, auth.uid(), 'mention' from unnest(ment) u
    where not exists (select 1 from public.message_mentions x where x.message_id = p_id and x.mentioned_user_id = u);
  delete from public.message_mentions where message_id = p_id and not (mentioned_user_id = any (ment));
  insert into public.message_mentions (message_id, mentioned_user_id, conversation_id)
    select p_id, u, m.conversation_id from unnest(ment) u on conflict do nothing;
end $$;

-- soft delete: the text and files disappear, a "message deleted" line stays so replies still make sense
create or replace function public.msg_delete(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare m public.messages; paths jsonb;
begin
  select * into m from public.messages where id = p_id;
  if m.id is null then raise exception 'Message not found'; end if;
  perform public.msg_require_member(m.conversation_id);
  if m.sender_id is distinct from auth.uid() and not public.is_admin() then raise exception 'You can only delete your own messages' using errcode = '42501'; end if;
  if m.message_type <> 'text' then raise exception 'This message can''t be deleted'; end if;
  select coalesce(jsonb_agg(file_path), '[]'::jsonb) into paths from public.message_attachments where message_id = p_id;
  update public.messages set content = '', deleted_at = coalesce(deleted_at, now()), deleted_by = auth.uid(), updated_at = now(), mentions_everyone = false where id = p_id;
  delete from public.message_mentions where message_id = p_id;
  delete from public.message_reactions where message_id = p_id;
  delete from public.pinned_messages where message_id = p_id;
  delete from public.message_notifications where message_id = p_id;
  return jsonb_build_object('files', paths);                 -- the app removes these files from storage
end $$;

create or replace function public.msg_react(p_id uuid, p_emoji text, p_on boolean default true) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.messages;
begin
  select * into m from public.messages where id = p_id;
  if m.id is null then raise exception 'Message not found'; end if;
  perform public.msg_require_member(m.conversation_id);
  if m.deleted_at is not null then raise exception 'That message was deleted'; end if;
  if p_emoji is null or length(p_emoji) not between 1 and 16 or p_emoji ~ '[\s<>"''&]' then raise exception 'Pick an emoji'; end if;
  if p_on then
    if (select count(distinct emoji) from public.message_reactions where message_id = p_id) >= 20
       and not exists (select 1 from public.message_reactions where message_id = p_id and emoji = p_emoji) then
      raise exception 'This message has the most reactions it can hold'; end if;
    insert into public.message_reactions (message_id, user_id, emoji, conversation_id) values (p_id, auth.uid(), p_emoji, m.conversation_id)
    on conflict do nothing;
  else
    delete from public.message_reactions where message_id = p_id and user_id = auth.uid() and emoji = p_emoji;
  end if;
  update public.messages set updated_at = now() where id = p_id;
end $$;

create or replace function public.msg_pin(p_id uuid, p_on boolean default true) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.messages;
begin
  select * into m from public.messages where id = p_id;
  if m.id is null then raise exception 'Message not found'; end if;
  perform public.msg_require_member(m.conversation_id);
  if m.deleted_at is not null or m.message_type <> 'text' then raise exception 'This message can''t be pinned'; end if;
  if p_on then
    if (select count(*) from public.pinned_messages where conversation_id = m.conversation_id) >= 50 then raise exception 'Up to 50 pinned messages per chat'; end if;
    insert into public.pinned_messages (conversation_id, message_id, pinned_by) values (m.conversation_id, p_id, auth.uid()) on conflict do nothing;
    if found then perform public.msg_system(m.conversation_id, 'pinned', '{}', jsonb_build_object('message', p_id)); end if;
  else
    delete from public.pinned_messages where message_id = p_id;
  end if;
  update public.messages set updated_at = now() where id = p_id;
end $$;

-- ---------------------------------------------------------------- reads (security invoker: row level security applies)
create or replace function public.msg_shape(m public.messages) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select jsonb_build_object(
    'id', m.id, 'conversation_id', m.conversation_id, 'sender_id', m.sender_id, 'client_op_id', m.client_op_id,
    'content', case when m.deleted_at is null then m.content else '' end, 'message_type', m.message_type, 'meta', m.meta,
    'mentions_everyone', m.mentions_everyone, 'created_at', m.created_at, 'edited_at', m.edited_at, 'deleted_at', m.deleted_at,
    'mentions', coalesce((select jsonb_agg(x.mentioned_user_id) from public.message_mentions x where x.message_id = m.id), '[]'::jsonb),
    'reactions', coalesce((select jsonb_agg(jsonb_build_object('emoji', r.emoji, 'user_id', r.user_id) order by r.created_at) from public.message_reactions r where r.message_id = m.id), '[]'::jsonb),
    'attachments', case when m.deleted_at is null then coalesce((select jsonb_agg(jsonb_build_object('id', a.id, 'name', a.file_name, 'path', a.file_path, 'type', a.file_type, 'size', a.file_size) order by a.created_at)
                     from public.message_attachments a where a.message_id = m.id), '[]'::jsonb) else '[]'::jsonb end,
    'pinned', exists (select 1 from public.pinned_messages p where p.message_id = m.id),
    'reply', (select jsonb_build_object('id', o.id, 'sender_id', o.sender_id, 'content', case when o.deleted_at is null then left(o.content, 240) else '' end,
                     'deleted', o.deleted_at is not null, 'files', (select count(*) from public.message_attachments a2 where a2.message_id = o.id))
              from public.messages o where o.id = m.reply_to_message_id))
$$;

-- newest first, cursor = (created_at, id) of the oldest message already on screen
create or replace function public.msg_history(p_conv uuid, p_before timestamptz default null, p_before_id uuid default null, p_limit integer default 40)
returns jsonb language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(public.msg_shape(m) order by m.created_at desc, m.id desc), '[]'::jsonb) from (
    select * from public.messages m
    where m.conversation_id = p_conv
      and (p_before is null or (m.created_at, m.id) < (p_before, coalesce(p_before_id, 'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid)))
    order by m.created_at desc, m.id desc limit least(greatest(coalesce(p_limit, 40), 1), 100)) m
$$;

-- everything around one message (opening a search result, a pin, a notification or a reply)
create or replace function public.msg_around(p_id uuid, p_each integer default 25)
returns jsonb language sql stable security invoker set search_path = '' as $$
  with t as (select * from public.messages where id = p_id),
  older as (select m.* from public.messages m, t where m.conversation_id = t.conversation_id and (m.created_at, m.id) <= (t.created_at, t.id)
            order by m.created_at desc, m.id desc limit least(greatest(p_each, 1), 60)),
  newer as (select m.* from public.messages m, t where m.conversation_id = t.conversation_id and (m.created_at, m.id) > (t.created_at, t.id)
            order by m.created_at, m.id limit least(greatest(p_each, 1), 60))
  select coalesce(jsonb_agg(public.msg_shape(x) order by x.created_at desc, x.id desc), '[]'::jsonb) from (select * from older union all select * from newer) x
$$;

create or replace function public.msg_get(p_ids uuid[]) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(public.msg_shape(m)), '[]'::jsonb) from public.messages m where m.id = any (p_ids)
$$;

create or replace function public.msg_overview() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(x order by (x->>'pinned')::boolean desc, x->>'last_message_at' desc), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', c.id, 'type', c.type, 'name', c.name, 'description', c.description, 'avatar_url', c.avatar_url, 'created_by', c.created_by,
      'created_at', c.created_at, 'last_message_at', c.last_message_at,
      'role', me.role, 'last_read_at', me.last_read_at, 'muted', me.is_muted, 'pinned', me.is_pinned, 'archived', me.is_archived,
      'members', (select jsonb_agg(jsonb_build_object('user_id', mm.user_id, 'role', mm.role, 'joined_at', mm.joined_at, 'last_read_at', mm.last_read_at,
                    'typing', mm.typing_at is not null and mm.typing_at > now() - interval '6 seconds') order by mm.joined_at)
                  from public.conversation_members mm where mm.conversation_id = c.id),
      'last', (select jsonb_build_object('id', l.id, 'sender_id', l.sender_id, 'content', left(l.content, 200), 'message_type', l.message_type, 'meta', l.meta,
                  'created_at', l.created_at, 'deleted', l.deleted_at is not null,
                  'files', (select count(*) from public.message_attachments a where a.message_id = l.id))
               from public.messages l where l.conversation_id = c.id order by l.created_at desc, l.id desc limit 1),
      'unread', (select count(*) from public.messages u where u.conversation_id = c.id and u.created_at > me.last_read_at
                   and u.sender_id is distinct from auth.uid() and u.deleted_at is null and u.message_type = 'text'),
      'mentions', (select count(*) from public.messages u where u.conversation_id = c.id and u.created_at > me.last_read_at and u.deleted_at is null
                   and u.sender_id is distinct from auth.uid()
                   and (u.mentions_everyone or exists (select 1 from public.message_mentions x where x.message_id = u.id and x.mentioned_user_id = auth.uid()))),
      'pinned_count', (select count(*) from public.pinned_messages p where p.conversation_id = c.id)
    ) x
    from public.conversations c join public.conversation_members me on me.conversation_id = c.id and me.user_id = auth.uid()
  ) s
$$;

create or replace function public.msg_pins(p_conv uuid) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(public.msg_shape(m) || jsonb_build_object('pinned_by', p.pinned_by, 'pinned_at', p.created_at) order by p.created_at desc), '[]'::jsonb)
  from public.pinned_messages p join public.messages m on m.id = p.message_id where p.conversation_id = p_conv
$$;

create or replace function public.msg_files(p_conv uuid, p_limit integer default 60) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', a.id, 'message_id', a.message_id, 'name', a.file_name, 'path', a.file_path, 'type', a.file_type,
           'size', a.file_size, 'uploaded_by', a.uploaded_by, 'created_at', a.created_at) order by a.created_at desc), '[]'::jsonb)
  from (select * from public.message_attachments where conversation_id = p_conv order by created_at desc limit least(greatest(p_limit, 1), 200)) a
$$;

-- messages that mention me (directly, or @everyone in my groups)
create or replace function public.msg_mentions(p_limit integer default 50) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(public.msg_shape(m) order by m.created_at desc), '[]'::jsonb) from (
    select m.* from public.messages m
    where m.deleted_at is null and m.sender_id is distinct from auth.uid()
      and (exists (select 1 from public.message_mentions x where x.message_id = m.id and x.mentioned_user_id = auth.uid()) or m.mentions_everyone)
    order by m.created_at desc limit least(greatest(p_limit, 1), 200)) m
$$;

create or replace function public.msg_search(p_q text, p_limit integer default 40) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(public.msg_shape(m) order by m.created_at desc), '[]'::jsonb) from (
    select m.* from public.messages m
    where length(btrim(coalesce(p_q, ''))) >= 2 and m.deleted_at is null and m.message_type = 'text'
      and (m.content ilike '%' || replace(replace(replace(btrim(p_q), '\', '\\'), '%', '\%'), '_', '\_') || '%'
           or exists (select 1 from public.message_attachments a where a.message_id = m.id
                      and a.file_name ilike '%' || replace(replace(replace(btrim(p_q), '\', '\\'), '%', '\%'), '_', '\_') || '%'))
    order by m.created_at desc limit least(greatest(coalesce(p_limit, 40), 1), 100)) m
$$;

create or replace function public.msg_notifications(p_limit integer default 40) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', n.id, 'conversation_id', n.conversation_id, 'message_id', n.message_id, 'actor_id', n.actor_id,
           'type', n.notification_type, 'is_read', n.is_read, 'created_at', n.created_at,
           'preview', (select left(m.content, 160) from public.messages m where m.id = n.message_id and m.deleted_at is null),
           'conversation', (select jsonb_build_object('type', c.type, 'name', c.name) from public.conversations c where c.id = n.conversation_id))
         order by n.created_at desc), '[]'::jsonb)
  from (select * from public.message_notifications where user_id = auth.uid() order by created_at desc limit least(greatest(p_limit, 1), 100)) n
$$;

-- who is online, judged by the database clock (a wrong clock on someone's computer can't make the whole team look offline)
create or replace function public.msg_presence() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'online', p.last_seen is not null and p.last_seen > now() - interval '2 minutes',
           'last_seen', p.last_seen)), '[]'::jsonb)
  from public.profiles p where p.active
$$;

-- ---------------------------------------------------------------- function permissions
do $$ declare f record; begin
  for f in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           where n.nspname = 'public' and p.proname like 'msg\_%' loop
    execute format('revoke all on function %s from public, anon', f.sig);
    execute format('grant execute on function %s to authenticated', f.sig);
  end loop;
end $$;
-- internal helpers are not part of the app's API
revoke execute on function public.msg_system(uuid, text, uuid[], jsonb) from authenticated;
revoke execute on function public.msg_require_member(uuid) from authenticated;

-- ---------------------------------------------------------------- files: a PRIVATE bucket
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('message-files', 'message-files', false, 26214400, array[
  'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/avif', 'image/heic',
  'application/pdf', 'text/plain', 'text/csv',
  'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/zip', 'application/x-zip-compressed', 'application/rtf', 'application/vnd.oasis.opendocument.text',
  'application/vnd.oasis.opendocument.spreadsheet', 'audio/mpeg', 'audio/mp4', 'video/mp4', 'video/quicktime'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists msgfiles_insert on storage.objects;
drop policy if exists msgfiles_select on storage.objects;
drop policy if exists msgfiles_delete on storage.objects;
-- upload: into <conversation you belong to>/<your own id>/...
create policy msgfiles_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'message-files' and (storage.foldername(name))[2] = auth.uid()::text
              and public.msg_is_member(public.msg_uuid((storage.foldername(name))[1])));
-- read: members of the conversation, unless the message holding the file was deleted
create policy msgfiles_select on storage.objects for select to authenticated
  using (bucket_id = 'message-files' and public.msg_file_open(name));
-- delete: your own uploads, or a Leafline admin
create policy msgfiles_delete on storage.objects for delete to authenticated
  using (bucket_id = 'message-files' and ((storage.foldername(name))[2] = auth.uid()::text or public.is_admin()));

-- ---------------------------------------------------------------- realtime (delivers only rows each person may read)
do $$ declare t text; begin
  foreach t in array array['conversations', 'conversation_members', 'messages', 'message_reactions', 'message_notifications', 'pinned_messages'] loop
    if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;

-- =================== 20261108000009_user_settings.sql ===================
-- Leafline 11.8 — 9th database update: your own account details follow you to every device.
-- Before this, name/email/phone/company typed in Settings > Account were kept only on the device where they were typed,
-- so the website, the desktop app and a second computer each showed their own copy (it looked like they never saved).
-- It also adds reactions on notes and scripts shared with the whole team (bottom of this file).
-- Safe to run more than once. Adds two tables and four functions; nothing existing is changed or removed.

create table if not exists public.user_settings (
  user_id    uuid primary key references public.profiles(id) on delete cascade,
  data       jsonb not null default '{}'::jsonb
             check (jsonb_typeof(data) = 'object' and length(data::text) <= 4000),
  updated_at timestamptz not null default now()
);
alter table public.user_settings enable row level security;

-- Private: each person reads and writes only their own row. Admins get nothing extra.
drop policy if exists user_settings_own on public.user_settings;
create policy user_settings_own on public.user_settings for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Both functions run as the caller (security invoker), so the policy above always applies.
create or replace function public.me_settings_get() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce((select jsonb_build_object('data', s.data, 'updated_at', s.updated_at)
                   from public.user_settings s where s.user_id = auth.uid()), '{}'::jsonb)
$$;

create or replace function public.me_settings_set(p_data jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare r public.user_settings;
begin
  if auth.uid() is null then raise exception 'Sign in first'; end if;
  if p_data is null or jsonb_typeof(p_data) <> 'object' then raise exception 'Settings must be an object'; end if;
  insert into public.user_settings (user_id, data, updated_at) values (auth.uid(), p_data, now())
  on conflict (user_id) do update set data = public.user_settings.data || excluded.data, updated_at = now()
  returning * into r;
  return jsonb_build_object('data', r.data, 'updated_at', r.updated_at);
end $$;

revoke all on function public.me_settings_get() from public, anon;
revoke all on function public.me_settings_set(jsonb) from public, anon;
grant execute on function public.me_settings_get() to authenticated;
grant execute on function public.me_settings_set(jsonb) to authenticated;

-- ---------------------------------------------------------------- reactions on shared notes and scripts
-- Anyone on the team can react to a note or script shared with the whole team. Private notes can't be reacted to.
create table if not exists public.note_reactions (
  note_id    uuid not null references public.notes(id) on delete cascade,
  user_id    uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  emoji      text not null check (emoji in ('👍','🔥','💡','🎉','❤️','😂')),
  created_at timestamptz not null default now(),
  primary key (note_id, user_id, emoji)
);
alter table public.note_reactions enable row level security;
drop policy if exists note_reactions_read on public.note_reactions;
create policy note_reactions_read on public.note_reactions for select to authenticated
  using (public.is_active() and exists (select 1 from public.notes n where n.id = note_id and n.scope = 'shared'));
-- no insert/update/delete policies: changes only go through note_react(), which checks everything.

create or replace function public.note_react(p_note uuid, p_emoji text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare added boolean;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if not exists (select 1 from public.notes where id = p_note and scope = 'shared') then
    raise exception 'Only notes and scripts shared with the team can have reactions';
  end if;
  if p_emoji is null or p_emoji not in ('👍','🔥','💡','🎉','❤️','😂') then raise exception 'Pick one of the listed reactions'; end if;
  delete from public.note_reactions where note_id = p_note and user_id = auth.uid() and emoji = p_emoji;
  added := not found;
  if added then insert into public.note_reactions (note_id, user_id, emoji) values (p_note, auth.uid(), p_emoji); end if;
  return jsonb_build_object('on', added);
end $$;

create or replace function public.note_reactions_for(p_notes uuid[]) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('note_id', x.note_id, 'emoji', x.emoji, 'n', x.n, 'mine', x.mine, 'who', x.who)), '[]'::jsonb)
  from (select r.note_id, r.emoji, count(*)::int as n, bool_or(r.user_id = auth.uid()) as mine,
               array_agg(p.display_name order by r.created_at) as who
        from public.note_reactions r join public.profiles p on p.id = r.user_id
        where r.note_id = any(p_notes) group by r.note_id, r.emoji) x
$$;

revoke all on function public.note_react(uuid, text) from public, anon;
revoke all on function public.note_reactions_for(uuid[]) from public, anon;
grant execute on function public.note_react(uuid, text) to authenticated;
grant execute on function public.note_reactions_for(uuid[]) to authenticated;

do $$ begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'note_reactions') then
    alter publication supabase_realtime add table public.note_reactions;
  end if;
exception when undefined_object then null;      -- no realtime publication (local test databases)
end $$;

-- =================== 20261108000010_banner_limit.sql ===================
-- Leafline 11.9 - 10th database update: profile banners up to 100 MB.
-- Raises the size limit of the 'media' storage bucket from 8 MB to 100 MB. The app still keeps profile pictures
-- to 8 MB; only banners may be larger. Safe to run more than once. Nothing is deleted.
-- Note: Supabase also has a project-wide upload limit (Storage > Settings). On the Free plan it is 50 MB and
-- cannot be raised, so banners between 50 and 100 MB need a paid plan with that limit set to 100 MB or more.
update storage.buckets set file_size_limit = 104857600 where id = 'media';

-- =================== 20261108000011_company_costs.sql ===================
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

-- =================== 20261109000012_phone_search.sql ===================
-- Leafline 11.11 - 12th database update: finding new leads from a phone (the website).
-- 1. Google Places: an admin saves the team's Google Places API key and a monthly limit. Every request to Google is
--    counted here first; when the month's limit is reached the database refuses, so the team can stay in Google's
--    free allowance (1,000 a month) no matter how many phones search.
-- 2. "Your PC runs it": when no key is set (or the limit is used up), a phone hands the search to the same person's
--    Leafline app on their PC, which runs the normal Google Maps search and uploads what it finds.
-- 3. Saving found businesses: one function adds them to the shared leads, skipping duplicates by phone number and
--    leaving out businesses someone already called (the same rules as the PC search).
-- Safe to run more than once. Adds three tables and nine functions; nothing existing is changed or removed.

-- ---------------------------------------------------------------- settings (one row) and the monthly counter
create table if not exists public.lead_settings (
  id         boolean primary key default true check (id),
  places_key text check (places_key is null or places_key ~ '^[A-Za-z0-9_-]{20,100}$'),
  month_cap  integer not null default 900 check (month_cap between 0 and 100000),
  updated_by uuid references public.profiles(id) on delete set null,
  updated_at timestamptz not null default now()
);
alter table public.lead_settings enable row level security;   -- no policies: only the functions below read or change it

create table if not exists public.lead_usage (
  month date primary key,                 -- first day of the month (America/Toronto)
  calls integer not null default 0 check (calls >= 0)
);
alter table public.lead_usage enable row level security;      -- no policies: only the functions below

create or replace function public.lead_month() returns date
language sql stable set search_path = '' as $$
  select date_trunc('month', (now() at time zone 'America/Toronto'))::date
$$;

-- everyone active: is phone search set up, how much of this month is used. The key itself is included because the
-- phone sends it to Google directly; the admin restricts it to the website's address in Google Cloud.
create or replace function public.lead_cfg() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare s public.lead_settings; used integer;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select * into s from public.lead_settings where id;
  select calls into used from public.lead_usage where month = public.lead_month();
  return jsonb_build_object('key', coalesce(s.places_key, ''), 'cap', coalesce(s.month_cap, 900), 'used', coalesce(used, 0),
                            'month', public.lead_month(), 'admin', public.is_admin());
end $$;

-- admins only. p_key: null keeps the saved key, '' removes it.
create or replace function public.lead_cfg_set(p_key text, p_cap integer) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k text := btrim(coalesce(p_key, ''));
begin
  if auth.uid() is null or not public.is_active() or not public.is_admin() then raise exception 'Only an administrator can change phone search settings'; end if;
  if p_key is not null and k <> '' and k !~ '^[A-Za-z0-9_-]{20,100}$' then raise exception 'That does not look like a Google API key'; end if;
  if p_cap is null or p_cap < 0 or p_cap > 100000 then raise exception 'The monthly limit must be between 0 and 100000'; end if;
  insert into public.lead_settings (id, places_key, month_cap, updated_by, updated_at)
  values (true, nullif(k, ''), p_cap, auth.uid(), now())
  on conflict (id) do update set
    places_key = case when p_key is null then public.lead_settings.places_key else nullif(k, '') end,
    month_cap = excluded.month_cap, updated_by = excluded.updated_by, updated_at = now();
  return public.lead_cfg();
end $$;

-- called just before each request to Google. Counts it, or refuses when the month's limit is reached.
create or replace function public.lead_quota_take() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare cap integer; used integer; m date := public.lead_month();
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  select month_cap into cap from public.lead_settings where id;
  cap := coalesce(cap, 900);
  insert into public.lead_usage (month, calls) values (m, 0) on conflict (month) do nothing;
  update public.lead_usage set calls = calls + 1 where month = m and calls + 1 <= cap returning calls into used;
  if not found then raise exception 'This month''s limit of % Google searches is used up', cap; end if;
  return jsonb_build_object('used', used, 'cap', cap);
end $$;

-- ---------------------------------------------------------------- saving businesses a phone found
-- p_rows: [{id, name, phone, address, website, rating, reviews, hours}], at most 100.
-- New phone number -> added. Same business not called yet -> moved into this search. Already called -> left out.
create or replace function public.lead_add_found(p_search text, p_btype text, p_rows jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r jsonb; pk text; ex record; ids text[] := '{}'; added integer := 0; moved integer := 0; skipped integer := 0;
  v_id text; v_name text; v_phone text; v_hours text;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p_search is null or length(btrim(p_search)) not between 1 and 300 then raise exception 'Missing search'; end if;
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) > 100 then raise exception 'Send 0 to 100 businesses'; end if;
  for r in select * from jsonb_array_elements(p_rows) loop
    v_id := btrim(coalesce(r->>'id', '')); v_name := btrim(coalesce(r->>'name', '')); v_phone := btrim(coalesce(r->>'phone', ''));
    v_hours := coalesce(r->>'hours', '');
    pk := right(regexp_replace(v_phone, '\D', '', 'g'), 10);
    if length(v_id) not between 1 and 300 or length(v_name) not between 1 and 200 or length(pk) < 7 or length(v_phone) > 40 then
      skipped := skipped + 1; continue;
    end if;
    if length(v_hours) > 2000 then v_hours := ''; end if;
    select id, status into ex from public.leads where id = v_id
      union all select id, status from public.leads where phone_key = pk and pk <> '' and id <> v_id
      limit 1;
    if found then
      if ex.status <> 'none' or ex.id = any(ids) then skipped := skipped + 1; continue; end if;   -- called, or already in this batch
      update public.leads set search = btrim(p_search), btype = left(coalesce(p_btype, ''), 80),
        rating = coalesce(nullif(left(r->>'rating', 10), ''), rating), reviews = coalesce(nullif(left(r->>'reviews', 12), ''), reviews),
        hours = case when v_hours <> '' then v_hours else hours end, updated_by = auth.uid()
      where id = ex.id;
      moved := moved + 1; ids := ids || ex.id;
    else
      insert into public.leads (id, name, phone, website, address, rating, reviews, hours, search, btype, added_at, added_by, source, updated_by)
      values (v_id, v_name, v_phone, coalesce(nullif(left(r->>'website', 500), ''), 'N/A'), coalesce(nullif(left(r->>'address', 300), ''), 'N/A'),
              coalesce(nullif(left(r->>'rating', 10), ''), 'N/A'), coalesce(nullif(left(r->>'reviews', 12), ''), 'N/A'), v_hours,
              btrim(p_search), left(coalesce(p_btype, ''), 80), now(), auth.uid(), 'google_places', auth.uid())
      on conflict do nothing;
      if found then added := added + 1; ids := ids || v_id; else skipped := skipped + 1; end if;
    end if;
  end loop;
  return jsonb_build_object('added', added, 'moved', moved, 'skipped', skipped,
    'rows', coalesce((select jsonb_agg(to_jsonb(l)) from public.leads l where l.id = any(ids)), '[]'::jsonb));
end $$;

-- ---------------------------------------------------------------- "your PC runs it"
create table if not exists public.lead_requests (
  id         uuid primary key default gen_random_uuid(),
  owner_id   uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  country    text not null default '' check (length(country) <= 80),
  state      text not null default '' check (length(state) <= 80),
  city       text not null default '' check (length(city) <= 80),
  btype      text not null check (length(btrim(btype)) between 1 and 80),
  q          text not null default '',
  status     text not null default 'pending' check (status in ('pending','running','done','failed','cancelled')),
  found      integer not null default 0 check (found >= 0),
  skipped    integer not null default 0 check (skipped >= 0),
  message    text not null default '' check (length(message) <= 300),
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  updated_at timestamptz not null default now()
);
create index if not exists lead_requests_owner_idx on public.lead_requests (owner_id, status, created_at);
alter table public.lead_requests enable row level security;
drop policy if exists lead_requests_read on public.lead_requests;
create policy lead_requests_read on public.lead_requests for select to authenticated using (owner_id = auth.uid() and public.is_active());
-- no write policies: only the functions below

create or replace function public.lead_req_json(r public.lead_requests) returns jsonb
language sql stable set search_path = '' as $$
  select jsonb_build_object('id', r.id, 'country', r.country, 'state', r.state, 'city', r.city, 'btype', r.btype, 'q', r.q,
    'status', r.status, 'found', r.found, 'skipped', r.skipped, 'message', r.message, 'created_at', r.created_at,
    'claimed_at', r.claimed_at, 'age_s', extract(epoch from now() - r.created_at)::integer)
$$;

-- a request nobody picked up within 30 minutes, or that stopped reporting for 15, is closed
create or replace function public.lead_req_expire() returns void
language sql security definer set search_path = '' as $$
  update public.lead_requests set status = 'failed', updated_at = now(),
    message = case when status = 'pending' then 'Your PC didn''t pick it up within 30 minutes. Open Leafline on your PC and try again.'
                   else 'Your PC stopped answering during the search.' end
  where owner_id = auth.uid() and ((status = 'pending' and created_at < now() - interval '30 minutes')
                                or (status = 'running' and updated_at < now() - interval '15 minutes'))
$$;

create or replace function public.lead_req_add(p_country text, p_state text, p_city text, p_btype text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.lead_requests; c text := btrim(coalesce(p_country, '')); s text := btrim(coalesce(p_state, ''));
  ci text := btrim(coalesce(p_city, '')); b text := btrim(coalesce(p_btype, ''));
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if length(b) not between 1 and 80 then raise exception 'Enter a business type'; end if;
  if c || s || ci = '' then raise exception 'Enter at least a country, state/province or city'; end if;
  if length(c) > 80 or length(s) > 80 or length(ci) > 80 then raise exception 'Keep each place name under 80 characters'; end if;
  perform public.lead_req_expire();
  if (select count(*) from public.lead_requests where owner_id = auth.uid() and status in ('pending','running')) >= 3 then
    raise exception 'You already have 3 searches waiting for your PC. Stop one first.';
  end if;
  insert into public.lead_requests (owner_id, country, state, city, btype) values (auth.uid(), c, s, ci, b) returning * into r;
  return public.lead_req_json(r);
end $$;

create or replace function public.lead_req_get(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.lead_requests;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  perform public.lead_req_expire();
  select * into r from public.lead_requests where id = p_id and owner_id = auth.uid();
  if not found then raise exception 'That search was not found'; end if;
  return public.lead_req_json(r);
end $$;

create or replace function public.lead_req_cancel(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  update public.lead_requests set status = 'cancelled', message = 'Stopped from your phone.', updated_at = now()
  where id = p_id and owner_id = auth.uid() and status in ('pending','running');
  return jsonb_build_object('ok', found);
end $$;

-- the PC app: take the oldest waiting search of the signed-in person (never anyone else's)
create or replace function public.lead_req_claim() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.lead_requests;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  perform public.lead_req_expire();
  select * into r from public.lead_requests where owner_id = auth.uid() and status = 'pending'
    order by created_at limit 1 for update skip locked;
  if not found then return null; end if;
  update public.lead_requests set status = 'running', claimed_at = now(), updated_at = now(), message = 'Your PC is starting the search...'
  where id = r.id returning * into r;
  return public.lead_req_json(r);
end $$;

-- the PC app: progress and the result. Says so if the phone stopped the search meanwhile.
create or replace function public.lead_req_update(p_id uuid, p_status text, p_found integer, p_skipped integer, p_text text, p_q text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare cur text;
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Sign in first'; end if;
  if p_status not in ('running','done','failed') then raise exception 'Bad status'; end if;
  select status into cur from public.lead_requests where id = p_id and owner_id = auth.uid() for update;
  if not found then raise exception 'That search was not found'; end if;
  if cur <> 'running' then return jsonb_build_object('ok', false, 'cancelled', cur = 'cancelled', 'status', cur); end if;
  update public.lead_requests set status = p_status, found = greatest(coalesce(p_found, 0), 0), skipped = greatest(coalesce(p_skipped, 0), 0),
    message = left(coalesce(p_text, ''), 300), q = left(coalesce(p_q, q), 300), updated_at = now()
  where id = p_id;
  return jsonb_build_object('ok', true, 'cancelled', false, 'status', p_status);
end $$;

revoke all on function public.lead_month() from public, anon;
revoke all on function public.lead_cfg() from public, anon;
revoke all on function public.lead_cfg_set(text, integer) from public, anon;
revoke all on function public.lead_quota_take() from public, anon;
revoke all on function public.lead_add_found(text, text, jsonb) from public, anon;
revoke all on function public.lead_req_json(public.lead_requests) from public, anon;
revoke all on function public.lead_req_expire() from public, anon, authenticated;
revoke all on function public.lead_req_add(text, text, text, text) from public, anon;
revoke all on function public.lead_req_get(uuid) from public, anon;
revoke all on function public.lead_req_cancel(uuid) from public, anon;
revoke all on function public.lead_req_claim() from public, anon;
revoke all on function public.lead_req_update(uuid, text, integer, integer, text, text) from public, anon;
grant execute on function public.lead_cfg() to authenticated;
grant execute on function public.lead_cfg_set(text, integer) to authenticated;
grant execute on function public.lead_quota_take() to authenticated;
grant execute on function public.lead_add_found(text, text, jsonb) to authenticated;
grant execute on function public.lead_req_add(text, text, text, text) to authenticated;
grant execute on function public.lead_req_get(uuid) to authenticated;
grant execute on function public.lead_req_cancel(uuid) to authenticated;
grant execute on function public.lead_req_claim() to authenticated;
grant execute on function public.lead_req_update(uuid, text, integer, integer, text, text) to authenticated;

-- =================== 20261110000013_meeting_checks.sql ===================
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

-- Check: how many calls each person now has (shown under the query when you press Run)
select p.display_name, count(c.*) as calls_on_record
from public.profiles p left join public.call_log c on c.employee_id = p.id
group by p.display_name order by calls_on_record desc;
