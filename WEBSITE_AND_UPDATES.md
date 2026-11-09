# Leafline: website, iPhone app, and automatic updates (v10.2)

You now have three ways to use the same app, all sharing one live database:

| | What it is | Updates |
|---|---|---|
| **Desktop app** (Windows) | the installer you already use | updates itself every time you open it |
| **Website** | https://YOUR-NAME.github.io/leafline/ | always the newest version when you open it |
| **iPhone/iPad home-screen app** | the website, added to your home screen | same as the website |

Everything (leads, calls, calendar, notes, deals, team numbers) is the same data everywhere, within a few seconds.
New businesses are still *found* in the desktop app (it uses a real browser to read Google Maps); they appear on the website and phones automatically.

---

## One-time setup (about 20 minutes)

### Step 1 · Add the new profile features to your database (1 minute)
1. Open your Supabase project, then **SQL Editor, New query**.
2. If you never ran it: open `supabase\migrations\20261106000003_avatars.sql`, copy everything, paste, **Run**.
3. Open `supabase\migrations\20261107000004_profile_extras.sql`, copy everything, paste, **Run**. It says "Success".
   (Until you do this, profile pictures/banners/bios still save on that device, they just aren't shared.)

### Step 2 · Make a GitHub home for the app (5 minutes)
1. Go to https://github.com and create a free account (skip if you have one).
2. Click **+** (top right), then **New repository**. Name it `leafline`. Choose **Public**. **Do not** tick "Add a README". Click **Create repository**.
   *Public is required for the free website. The app's code is public, but your data is not: it lives in Supabase behind the logins. The only key in the code is the public one that is meant to be public, and the private key never leaves `tools\.env` on your PC (the publish tool refuses to send it).*
3. Double-click **`SETUP_GITHUB.bat`** and type your GitHub username.

### Step 3 · Publish (5 minutes the first time)
1. Install **Git** once from https://git-scm.com/download/win (click Next through everything).
2. Double-click **`PUSH_UPDATE.bat`**. The first time, a window asks you to sign in to GitHub: do that.
3. It uploads the website and starts building the desktop update online (about 8 minutes, you can close the window).

### Step 4 · Turn the website on (1 minute)
1. On GitHub, open your `leafline` repository, then **Settings**, then **Pages** (left menu).
2. Under **Build and deployment**, set **Source = Deploy from a branch**, **Branch = main**, folder **/docs**, then **Save**.
3. After about a minute the page shows your address: `https://YOUR-NAME.github.io/leafline/`. Open it and sign in with your normal username and password.

### Step 5 · Put it on your iPhone (1 minute)
1. Open the address in **Safari** (it must be Safari).
2. Tap the **Share** button (square with an arrow), scroll, tap **Add to Home Screen**, then **Add**.
3. Open it from the new Leafline icon. It opens full screen like a normal app and stays signed in.
(Android: Chrome menu, **Install app**. iPad works the same as iPhone.)

### Step 6 · Rebuild the desktop installer once (10 minutes)
Do this once so the desktop app knows where to find updates. After this it updates itself.
1. Double-click **`build_windows.bat`** (same as before). Install the new `Leafline-Lead-Finder-Setup-10.2.0.exe` over the old one. Your data is untouched.

---

## Every time you want to push an update
1. Get the new files (from me) into your project folder.
2. Double-click **`PUSH_UPDATE.bat`**, type a short note (or just press Enter).

That's it:
* **Website and phones** update within about a minute. Open the app (or bring it back from the background) and it refreshes itself.
* **Desktop apps** update the next time each person opens the app: a short "Downloading update" screen, then it restarts into the new version. If a PC is already open, it shows an "Update ready, Restart" button.
* The desktop only gets a new version when `version` in `package.json` goes up (I bump it for you whenever there is a desktop change). Website changes need no version bump.

**Check for updates button:** Account & Settings, then **App & updates**. It exists in the desktop app and on the website.

---

## New: profiles
Account & Settings, then **Your public profile**: banner picture, job title, mood, bio, profile colour, and **thought of the day**.
Everyone sees them on the **Team** page: a "Thoughts of the day" strip, and each person's card shows title, mood, bio and thought; click a card to open their full profile with the banner. Thoughts disappear after 24 hours and mood/bio stay until you change them.

---

## If something goes wrong
* **PUSH_UPDATE says "repository does not exist" or "rejected"**: the repository must be new and empty (no README). Create a new one and run `SETUP_GITHUB.bat` again.
* **Website shows an old version**: pull down to refresh, or close and reopen the app. It also checks by itself when you come back to it.
* **Desktop says "This build was made without an update address"**: run `SETUP_GITHUB.bat`, then `build_windows.bat` again.
* **A desktop update doesn't install**: the app keeps working on the old version, and Account & Settings shows why. It won't try the same failing update more than once a day.
* **Phone can't reach the app**: it opens offline from what it saved last, shows "Offline", and uploads your changes when the connection returns.
* Your daily backups: keep using `ADMIN_TOOLS.bat`, then Backup. (The automatic cloud backup in `optional_private_repo` must never be put in this public repository.)
