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
