-- OPTIONAL third migration: profile pictures that the whole team can see (Team page).
-- Pictures are stored as small (about 192x192) images inside the profile row; no extra storage service is needed.
alter table public.profiles add column if not exists avatar text
  check (avatar is null or (length(avatar) < 60000 and avatar ~ '^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$'));
