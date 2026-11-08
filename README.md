# Leafline Lead Finder - installer project (v9)

Electron window + the same Python engine as before (Google Maps scraping, SQLite, owner lookup).
Your existing data in `~\LeaflineLeadFinder` is picked up automatically.

## Folder layout matters
Open a terminal INSIDE the `leafline-app` folder (the one that contains `main.js` and `package.json` with the name `leafline-lead-finder`).
Do not run `npm init` or `npm install <something>` in a parent folder: that creates a second, wrong `package.json` and `package-lock.json`
(name `leafline-installer-project`, main `index.js`) and `npm start` then fails. If you have those, delete them.
For GitHub, upload the CONTENTS of `leafline-app` so that `.github/workflows/build.yml` and `package.json` sit at the top level of the repo.

## Easiest way: let GitHub build both installers (no tools needed on your PC)
1. Create a GitHub repo (private is fine) and upload everything in this folder, including the hidden `.github` folder.
2. Open the repo > Actions > "Build installers" > Run workflow.
3. In about 10 minutes download from the run's Artifacts:
   - `windows-exe`  -> Leafline-Lead-Finder-Setup-10.1.0.exe
   - `mac-dmg-apple-silicon` / `mac-dmg-intel` -> the .dmg for M1-M4 Macs / older Intel Macs

## Build it yourself
- Windows: install Python 3.10+ (tick "Add to PATH") and Node.js LTS once, then double-click `build_windows.bat`. It builds `dist\Leafline-Lead-Finder-Setup-10.1.0.exe` and opens that folder. Run that .exe to install the app (Start Menu + desktop shortcut, opens in its own window, not a browser).
- Mac (must be run on a Mac): `./build_mac.sh`. DMG lands in `dist/`.
- A DMG cannot be built on Windows, and an .exe is best built on Windows, so the GitHub route is simplest.

## Try it without installing
Double-click `run_dev.bat` (Mac/Linux: `./run_dev.sh`). It installs what is missing, then opens the app.

## If the build says "spawn EPERM"
Windows or your antivirus blocked the installer tool. build_windows.bat now copies the project to %LOCALAPPDATA%\LeaflineBuild (outside Downloads) and, if still blocked, asks Windows (one UAC prompt) to exclude only that folder from Defender. With a third-party antivirus, add that folder as an exclusion yourself.

## If it doesn't open
The app writes everything the engine prints to `engine.log`:
Windows `%APPDATA%\\Leafline Lead Finder\\engine.log`, Mac `~/Library/Application Support/Leafline Lead Finder/engine.log`. Send me that file.

## Notes
- Needs Microsoft Edge or Google Chrome installed on the computer (the scraper opens it, as before).
- The installers are unsigned. Windows SmartScreen: "More info" > "Run anyway". Mac: right-click the app > Open the first time.
  Removing those warnings needs paid code-signing certificates (Windows) / an Apple Developer account (Mac).
- Settings like colors live in the `:root` block of `UI_HTML` inside `backend/leafline_backend.py`.


## Shared team database (v10)
See `SETUP_SUPABASE.md`. Employees sign in with their own account; all leads, deals and calendar events sync through Supabase. Tests: `python tests/test_sync.py`, `tests/test_ui.py`, `tests/test_import.py` (run against a built-in fake server, no internet needed).

## What is new in 10.1
- **Notes & Scripts** (sidebar): private notes, notes shared with the team, and a Google-Docs-style script editor (bold, italic, underline, strikethrough, colours, highlight, font and size, headings, bullets, numbering, alignment, links, undo/redo, paste with formatting). Everything saves by itself.
- **Script panel**: press the page icon at the top (or Ctrl+J) to keep a script open beside your phone numbers on Find Leads, Called Leads or the Calendar. Drag its edge to resize, A- / A+ for text size, search inside it.
- **Call Log**: every call, by every employee, with filters (employee, date, outcome, business/phone) and a "Log a call" button for the seven outcomes.
- **Admin** (James, Omar, Akbar only): daily targets, roles, activate/deactivate, everyone's numbers, export of company data.
- **Calendar**: Month / Week / Day views, event types (meeting, follow-up, scheduled call, task) and tick-off for tasks.
- `ADMIN_TOOLS.bat`: add an employee, reset a password, reactivate, back up (needs `tools\.env`, admin computer only).
- Tests: `python tests/test_features.py` and `tests/test_ui_features.py` as well as the three older ones.

Optional: run `supabase/migrations/20261106000002_tasks.sql` once in the Supabase SQL editor to switch on "tasks done" on the Team page. The app works without it.

## 10.1 additions
- **Profile pictures:** Account > Upload photo (JPG/PNG/WebP, any size; it is cropped square and shrunk). Everyone sees everyone's picture on the Team page. To share them, run `supabase/migrations/20261106000003_avatars.sql` once in the Supabase SQL editor; until then a picture only shows on your own computer.
- **Meetings from Called Leads:** every "Meeting set up" card has an *Add to calendar* button (or shows its date), and the column has an *Add* button to schedule any called business, with one-click times (today, tomorrow, in 2 days, next week).
- The script button now sits right next to the notification bell.


## v10.2: website, phone app, automatic updates, richer profiles
See **WEBSITE_AND_UPDATES.md**. The website is generated from the same interface file as the desktop app (`python tools/build_web.py` writes the `docs/` folder) and talks straight to Supabase through `web_src/engine.js`. Desktop updates use electron-updater with GitHub Releases (`updater.js`, `github_workflows/release.yml`).

## What is new in 11.3
- **Confirm payment** (Profits page and Calendar): a deal payment only counts toward money made (Profits, Dashboard, leaderboard) after someone presses **Confirm** once the money is really in. Payments whose date passed without a confirmation are listed under **Waiting for confirmation**. Run `supabase/migrations/20261108000007_confirm_payments.sql` once (it is also in `RUN_IN_SUPABASE.sql`) so confirmations are shared with the team.
- **Call Log animations**: rows cascade in, new calls glow when they arrive, counts tick up, filters and chips respond to touch.
- **Called Leads groups fold away**: click a group header (for example "Home renovation" under Meeting set up) to hide it; it stays hidden until you open it again. The arrow next to each column's count folds or opens every group in that column.
- **Phone layout pass**: every text box is 16px so iPhones no longer zoom in, bigger tap targets, call-log filters in two columns, the Settings save row and data-folder path no longer run off the screen, the lead pop-up gives the owner box a full row and the results a 2 x 2 grid, the Team page's Online label no longer sits in a stray box, and the calendar header and More menu fit on 320px phones.
- Browser tests can run on Windows: set `LEAFLINE_CHROME` to Chrome or Edge (for example `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`). New test: `python tests/test_payments.py`.

## What is new in 11.4: Messages
Team chat inside Leafline (sidebar > **Messages**, also on phones and the website):
- Direct messages with anyone on the team, and group chats (name, description, picture, add/remove people, leave).
- @mentions with a picker (stored as real references, so renaming someone never breaks them), and @everyone for
  group owners/admins. Mentions get highlighted, counted, notified and listed under the **Mentions** tab.
- Reactions, replies (click the preview to jump to the original), edit, delete, pinned messages, formatting
  (**bold**, *italic*, ~~strike~~, `code`, lists, links), a searchable emoji picker with recently used emoji.
- Files and screenshots: drag and drop, paste, or the + button; upload progress, picture previews, downloads.
- Read receipts, typing indicators, online status, unread and mention badges, a notifications list, mute,
  pin and archive per chat, search across chats, people and messages.
- Live: new messages arrive within about a second (Supabase Realtime), with automatic fallback to checking every
  few seconds. Messages written without a connection wait on the device and send themselves once it is back.
- **Setup:** run `supabase/migrations/20261108000008_messaging.sql` once (it is also in `RUN_IN_SUPABASE.sql`).
  Details in SETUP_SUPABASE.md.
- **Tests:** `cd tests/pg && npm install` once, then `node test_messaging_sql.mjs` (security rules on a real
  Postgres) and `python tests/test_messages.py` (three people chatting at once in the app and on the website).

## What is new in 11.5: call streaks
- A streak grows by one for every workday someone makes at least **25 calls**. Weekends never break it, and 25 calls on a
  weekend counts as a bonus day. Today never breaks it either: until midnight the streak still counts from yesterday.
  Missing a workday, even by one call, starts it over. (The 25 is `STREAK_GOAL` in backend/leafline_backend.py.)
- Colours: 3 days yellow (Spark), 5 orange, 10 dark orange, 15 red, 20 dark red, 30 purple, 45 dark purple, 60 blue.
- Every card on the Team page shows that person's streak under their latest activity: a gradient bar with the milestones
  (reached ones lit, the next one dashed, the rest grey), today's progress out of 25 and their best streak.
- The flame badge also shows next to names on Team cards, profile hover cards (including in Messages), profile pop-ups
  and the Messages details panel. No database update needed.
