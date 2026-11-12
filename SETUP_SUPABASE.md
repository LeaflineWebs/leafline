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

**Kyle and Mubaraq (11.15):** `ADMIN_TOOLS.bat` > option 6 (or `python tools/seed_users.py starters`). They are
created the same way as everyone else: a sign-in plus a team profile, role **employee** (not admin), a random temporary
password printed once, and a forced password change at first sign-in. Anyone who already exists is skipped. Then
option 5 (`verify_db.py`) checks their role and that every sign-in has a team profile (and the other way round).

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

## Sixth migration (Leafline 11.1: old calls count again + moving credit)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261107000006_credit.sql` > Run. Safe to run twice. Run it after migration 5.
- **Old calls come back into the numbers.** Calls from before the call log existed (the imported history, and any business marked
  before logging started) now count on the Team page and the leaderboard, for the person each business is credited to.
  When you press Run, a small table shows how many calls each person now has on record.
- **"Credited to"** on Called Leads and on deals: give a meeting you booked to a teammate, or claim one someone booked for you.
  Only the person who has it, the person it's for, or an admin can move it, and every move shows in the team Activity feed.
  The call itself stays with whoever dialled; only the meeting or sale moves.

## Seventh migration (Leafline 11.3: confirm payments)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261108000007_confirm_payments.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.)
- A deal payment now counts toward "money made" (Profits, Dashboard, leaderboard) only after someone presses **Confirm** on it.
  A payment whose date passed without a confirmation shows under **Waiting for confirmation** on the Profits page.
- Until it is run, confirmations stay on the computer that made them and upload by themselves afterwards.
  On the website, Confirm asks for this update first.

## Eighth migration (Leafline 11.4: Messages)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261108000008_messaging.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.) Run migrations 1 to 7 first.
- **Tables:** `conversations`, `conversation_members`, `messages`, `message_mentions`, `message_reactions`,
  `message_attachments`, `message_notifications`, `pinned_messages`. Nothing existing is changed or deleted.
- **Security:** row level security on every table. People only read conversations they belong to. Nobody writes
  to these tables directly: every change goes through a `msg_*` database function that checks who is calling,
  that they are an active teammate and that they belong to the conversation. The sender is always the caller.
- **Files:** a new PRIVATE Storage bucket `message-files` (25 MB per file; images, PDF, Office files, text, CSV,
  zip, audio and video). Files sit under `<conversation id>/<uploader id>/` and only that conversation's members
  can upload or read them, through links that expire after an hour.
- **Live updates:** the migration adds the messaging tables to Supabase Realtime (`supabase_realtime` publication).
  If Realtime is switched off for the project, Messages still works and checks for new messages every few seconds.
- No new environment variables or keys. The app keeps using the publishable key and each person's own sign-in.
- Group pictures go into the existing public `media` bucket (from migration 5), in the uploader's own folder.
- Until it is run, the Messages page explains that this update is needed; everything else keeps working.

## Ninth migration (Leafline 11.8: account details on every device, reactions on shared notes)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261108000009_user_settings.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.)
- Adds one private table, `user_settings`: each person can read and write only their own row (admins included).
  It holds what you type in Settings > Account (name, email, phone, company, role, country, goals), so it shows
  up on the website, the desktop app and any other computer you sign in on.
- Two functions, `me_settings_get` and `me_settings_set`, run as the signed-in person, so the privacy rule always applies.
- Also adds `note_reactions`: teammates can react (👍 🔥 💡 🎉 ❤️ 😂) to notes and scripts shared with the whole team.
  Reactions only change through `note_react`, which checks the note is shared and the person is an active teammate.
- Nothing existing is changed. Until it is run, account details stay on the device where they were typed and
  the reaction bar stays hidden.

## Tenth migration (Leafline 11.9: banners up to 100 MB)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261108000010_banner_limit.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.)
- Raises the `media` bucket's size limit from 8 MB to 100 MB. The app keeps profile pictures at 8 MB; banners may be up to 100 MB.
- Supabase also has a project-wide upload limit: Storage > Settings > "Upload file size limit". On the Free plan it is
  50 MB and can't be raised, so banners over 50 MB need a paid plan with that limit set to at least 100 MB.

## Fourteenth migration (Leafline 11.15: invoices and team cards)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261111000014_invoices_team.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.) Nothing existing is changed or removed.
- Adds `invoices` and `invoice_templates`, plus the invoice settings (company details, tax, e-Transfer email) as the
  `invoice` row of the existing `settings` table.
- Who sees what: admins see every invoice; everyone else sees only invoices they made. Every active teammate can create
  invoices and use templates. Only admins mark invoices paid, void them, and change templates and invoice settings.
  There are no direct write rules on either table: every change goes through checked `inv_*` functions, totals are
  calculated in the database, and every change goes into the audit log. Templates are archived, never deleted.
- Adds department, responsibilities, skills, work phone and work email to profiles (`team_cards`, `team_card_set`):
  you edit your own card, admins can edit anyone's, every active teammate can read them.
- After running it: open **Invoices > Settings** in the app (admin) and fill in the e-Transfer email and company details.
  Leave the tax rate at 0 unless the business is registered for HST.

## Thirteenth migration (Leafline 11.13: confirming meetings)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261110000013_meeting_checks.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.)
- Adds `meeting_checks`: which meeting (business + meeting time, as shown in the app) was confirmed, by whom and when.
- Everyone on the team can read it. `mtg_confirm` / `mtg_unconfirm` let any active teammate confirm or undo a meeting
  whose time has passed; there are no direct write rules, and every change goes into the audit log.

## Twelfth migration (Leafline 11.11: finding new leads on phones)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261109000012_phone_search.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.)
- `lead_settings` (one row): the team's Google Places API key and a monthly request limit (default 900). Only admins
  change it (`lead_cfg_set`); every active teammate can read it through `lead_cfg`, because the phone sends the key to
  Google directly. Restrict the key to your website's address in Google Cloud (Settings > Finding leads on phones >
  How to get a free key shows the steps).
- `lead_usage`: Google requests counted per month. `lead_quota_take` adds one before every request and refuses once the
  limit is reached, for the whole team together.
- `lead_add_found`: saves what a phone found. One lead per phone number; businesses someone already called are left out.
- `lead_requests`: searches a phone hands to the same person's Leafline app on their PC (when no key is saved, or the
  limit is used up). Only the owner can see or stop them, and only their own PC picks them up; unclaimed ones expire
  after 30 minutes.
- No table has write rules: all changes go through those functions, which check the caller is signed in and active.

## Eleventh migration (Leafline 11.10: company costs)
Supabase > SQL Editor > New query > paste `supabase/migrations/20261108000011_company_costs.sql` > Run. Safe to run twice.
(`RUN_IN_SUPABASE.sql` already contains it.)
- Adds the `expenses` table: company costs (what it was, amount, date, whose money it comes off, who added it).
- Everyone on the team can read it. Only administrators can add or remove costs, through `exp_add` and `exp_delete`,
  which check the caller is an active admin. There are no direct write rules, and every change goes into the audit log.
- Each cost is taken off the money made in its month (Profits, Dashboard) and off that person's leaderboard money.
