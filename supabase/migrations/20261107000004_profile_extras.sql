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
