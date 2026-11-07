# Leafline shared database: setup order (about 30 minutes, $0)

Project: `yvpmgmuthrmzievgdifw`. The app already contains the URL and the PUBLISHABLE key (safe to ship; row level security
protects the data). The SECRET key lives only in `tools/.env` on an admin PC.

## Step 1. Admin PC: put the secret key in place
In `tools`, copy `.env.example` to `.env` and paste the secret key after `SUPABASE_SECRET_KEY=`. Never commit or share it.
Rotate it (Project Settings > API) when setup is finished, because it has been pasted in chat.
```
pip install requests
python verify_db.py
```
`verify_db.py` checks every table exists, that anonymous visitors can see NOTHING (proves row level security is on), and the six accounts/roles.
At this point it will list the accounts as missing. That's expected until step 2. Send me any other FAIL line.

## Step 2. Create the six accounts
```
python seed_users.py seed
python verify_db.py --as gio Gio123
```
James, Omar and Akbar are administrators; Gio, Jaylen and Tim are reps. Logins are `gio@leaflineweb.com` (placeholder, never emailed); people type `gio`.
Starter passwords are Gio123, James123, ... and each person must choose a new one at first sign-in. After that the `--as` test
needs the new password. The `--as` run proves a rep can read shared data but cannot read the audit log, change daily targets, or make himself admin.

## Step 3. Install the new app and test with two people
Build with `build_windows.bat` and install over the old version. Sign in as two different employees on two PCs and confirm a change on one
appears on the other within a few seconds. Existing local data on each PC is kept; it uploads in the background the first time that person signs in
(anything that differs from the shared copy is archived locally in `sync_conflicts`, never overwritten silently).

## Step 4. BACK UP THE ORIGINALS, then import (nothing is imported until you do this)
1. On James's PC and Akbar's PC: close Leafline, then copy the WHOLE folder `%USERPROFILE%\LeaflineLeadFinder` to a USB stick or cloud drive. Copy, don't move.
2. Import only from the COPIES:
```
python import_legacy.py "C:\path\akbar\leads_v2.db"                         # dry run, read the report
python import_legacy.py "C:\path\akbar\leads_v2.db" --apply --owner akbar
python import_legacy.py "C:\path\james\leads_v2.db" --apply --owner james
```
The importer also makes its own hash-checked copy and a full export of the shared database first. It never overwrites; re-running adds nothing.
Duplicates (same Google id or phone across files) are archived in `legacy_duplicates`; the copy with call work is kept.
Old files kept only each lead's LAST result, so they become one flagged record per worked lead that is NOT counted in "calls today".
Meetings marked set up with no date are listed in the report: add them to the calendar by hand.

## Step 5. Backups and keep-alive (recommended)
Private GitHub repo + secrets `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (the secret key). `.github/workflows/backup-keepalive.yml` exports every shared table daily
(personal notes excluded) and touches the database so the free project is not paused for inactivity.

## What the free plan means (honest version)
500 MB database; paused after 7 days of no activity (the daily job prevents it but is not a guarantee); no built-in backups (the daily export is yours);
no uptime guarantee. Pro is $25/month if this becomes too risky.
Sync: changes upload within seconds; the app checks for others' changes about every 4 seconds (polling). If the internet drops, changes wait safely on that PC.
Who can edit what: any employee can edit leads and deals; an event can be edited by its creator, the person it's assigned to, or an admin; only admins can delete leads and deals.

## Optional second migration (tasks done)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261106000002_tasks.sql` > Run. Safe to run twice.
Until then calendar ticks stay on the computer that made them; afterwards they upload on their own (nothing is lost).

## Adding people later
Double-click `ADMIN_TOOLS.bat` on the admin computer. Deactivating is done inside the app (Admin page).

## Optional third migration (profile pictures)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261106000003_avatars.sql` > Run. Safe to run twice.

## Optional fourth migration (profile extras)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261107000004_profile_extras.sql` > Run. Safe to run twice.

## Fifth migration (Leafline 11: Announcements, animated pictures, leaderboard guard)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261107000005_board_posts_media.sql` > Run. Safe to run twice.
It adds:
- the **Announcements & ideas** board (posts, comments, reactions). Everyone on the team can post, edit and delete any post (your rule); the original author can never be changed and every edit records who made it.
- a free **Storage bucket called `media`** for profile pictures and banners in GIF, WebP, PNG, JPEG or AVIF (8 MB max each, no SVG). People can only write into their own folder. The free plan includes 1 GB of storage.
- a **deal guard**: only an admin can give a deal to someone else or move it between people, so nobody can pump up their "Most Money Made" ranking.
Until it is run, the Announcements page says so, pictures upload as still images, and everything else keeps working.
Run migrations 3 and 4 first if you haven't.
