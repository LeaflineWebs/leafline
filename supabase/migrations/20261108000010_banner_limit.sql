-- Leafline 11.9 - 10th database update: profile banners up to 100 MB.
-- Raises the size limit of the 'media' storage bucket from 8 MB to 100 MB. The app still keeps profile pictures
-- to 8 MB; only banners may be larger. Safe to run more than once. Nothing is deleted.
-- Note: Supabase also has a project-wide upload limit (Storage > Settings). On the Free plan it is 50 MB and
-- cannot be raised, so banners between 50 and 100 MB need a paid plan with that limit set to 100 MB or more.
update storage.buckets set file_size_limit = 104857600 where id = 'media';
