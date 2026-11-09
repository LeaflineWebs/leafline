"use strict";
// Automatic updates for the desktop app (GitHub Releases).
// On launch: look for a newer version; if there is one, download it and install it right away (before the app opens),
// unless that same update already failed once. While the app is open: "Check for updates" in Account & Settings.
// Windows: electron-updater. Mac: an unsigned app can't use electron-updater, so it updates itself (see macCheck and
// mac_update.js): download the .zip listed in latest-mac-<arm64|x64>.yml, check its SHA-512, and swap it in when the app restarts.
const { app, ipcMain } = require("electron");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const MAC = process.platform === "darwin";
let autoUpdater = null, loadError = "";
if (!MAC) { try { ({ autoUpdater } = require("electron-updater")); } catch (e) { loadError = e.message; } }

const state = { state: "idle", version: app.getVersion(), latest: "", percent: 0, error: "" };
let retryT = null;
let sendTo = () => {}, installing = false;

function guardFile() { return path.join(app.getPath("userData"), "update-attempt.json"); }
function readGuard() { try { return JSON.parse(fs.readFileSync(guardFile(), "utf8")); } catch (_) { return {}; } }
function writeGuard(o) { try { fs.writeFileSync(guardFile(), JSON.stringify(o)); } catch (_) {} }

function set(patch) { Object.assign(state, patch); try { sendTo({ ...state }); } catch (_) {} }

function configured() {
  // electron-builder writes resources/app-update.yml only when a GitHub repository was set at build time
  try { return fs.existsSync(path.join(process.resourcesPath, "app-update.yml")); } catch (_) { return false; }
}

function init(win, log) {
  sendTo = (s) => { try { if (win() && !win().isDestroyed()) win().webContents.send("update-status", s); } catch (_) {} };
  ipcMain.handle("app-info", () => ({ version: app.getVersion(), platform: "desktop" }));
  ipcMain.handle("update-status", () => ({ ...state }));
  ipcMain.handle("update-install", () => { install(); return true; });
  ipcMain.handle("update-check", async () => { await check(false); return { ...state }; });
  if (MAC) return;
  if (!autoUpdater) { log("updater not available: " + loadError + "\n"); return; }
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.allowPrerelease = false;
  autoUpdater.logger = { info: (m) => log("[update] " + m + "\n"), warn: (m) => log("[update] " + m + "\n"), error: (m) => log("[update] " + m + "\n"), debug() {} };
  autoUpdater.on("checking-for-update", () => set({ state: "checking", error: "" }));
  autoUpdater.on("update-available", (i) => set({ state: "downloading", latest: i.version, percent: 0 }));
  autoUpdater.on("update-not-available", () => set({ state: "none", percent: 0 }));
  autoUpdater.on("download-progress", (p) => set({ state: "downloading", percent: p.percent || 0 }));
  autoUpdater.on("update-downloaded", (i) => set({ state: "ready", latest: i.version, percent: 100 }));
  autoUpdater.on("error", (e) => {
    const msg = String((e && e.message) || e);
    // The version tag reaches GitHub straight away, but the installer takes ~10 minutes to build online.
    // In between, GitHub has the new version number but no files yet: that's "still building", not a failure.
    if (/latest\.yml|404|HttpError: 404/i.test(msg)) { building(); return; }
    set({ state: "error", error: "Couldn't update: " + msg.slice(0, 160) });
  });
}

function building() {
  set({ state: "building", error: "" });
  clearTimeout(retryT); retryT = setTimeout(() => check(true), 5 * 60 * 1000);
}

// ---------------------------------------------------------------- Mac
const mac = { file: "", version: "", busy: null };
function repoInfo() {
  try {
    const y = fs.readFileSync(path.join(process.resourcesPath, "app-update.yml"), "utf8");
    const o = /^owner:\s*['"]?([A-Za-z0-9-]+)/m.exec(y), r = /^repo:\s*['"]?([A-Za-z0-9._-]+)/m.exec(y);
    return o && r ? { owner: o[1], repo: r[1] } : null;
  } catch (_) { return null; }
}
function newer(a, b) {
  const x = String(a).split(".").map((n) => parseInt(n, 10) || 0), y = String(b).split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  return false;
}
function parseMacYml(t) {
  const version = (/^version:\s*['"]?([\d.]+)/m.exec(t) || [])[1] || "", files = []; let cur = null;
  for (const line of String(t).split(/\r?\n/)) {
    let m;
    if ((m = /^\s*-\s*url:\s*['"]?([^'"\s]+)/.exec(line))) { cur = { url: m[1] }; files.push(cur); }
    else if (cur && (m = /^\s+sha512:\s*['"]?([A-Za-z0-9+/=]+)/.exec(line))) cur.sha512 = m[1];
    else if (cur && (m = /^\s+size:\s*(\d+)/.exec(line))) cur.size = +m[1];
    else if (/^\S/.test(line)) cur = null;
  }
  return { version, files };
}
function macAppPath() { const p = path.resolve(process.execPath, "..", "..", ".."); return p.endsWith(".app") ? p : ""; }

function macCheck() {
  if (mac.busy) return mac.busy;
  mac.busy = (async () => {
    try {
      const r = repoInfo();
      if (!r) return set({ state: "error", error: "This build was made without an update address. Rebuild the Mac app once." });
      set({ state: "checking", error: "" });
      const base = `https://github.com/${r.owner}/${r.repo}/releases`;
      let res;
      const arch = process.arch === "arm64" ? "arm64" : "x64";   // Apple Silicon or Intel: each has its own build and update list
      try { res = await fetch(`${base}/latest/download/latest-mac-${arch}.yml`, { cache: "no-store" }); }
      catch (e) { return set({ state: "error", error: "Couldn't reach GitHub to check for updates. Check your internet connection." }); }
      if (res.status === 404) return building();                 // the Mac files are still being built online
      if (!res.ok) return set({ state: "error", error: `Couldn't check for updates (GitHub answered ${res.status}).` });
      const info = parseMacYml(await res.text());
      if (!info.version || !newer(info.version, app.getVersion())) return set({ state: "none", percent: 0 });
      if (mac.file && mac.version === info.version && fs.existsSync(mac.file)) return set({ state: "ready", latest: info.version, percent: 100 });
      const f = info.files.find((x) => /\.zip$/i.test(x.url) && (arch === "arm64" ? /arm64/.test(x.url) : !/arm64/.test(x.url)));
      if (!f || !f.sha512) return set({ state: "error", error: "The Mac update isn't complete online yet. It will try again later." });
      const where = macAppPath();
      if (!where || where.includes("/AppTranslocation/") || where.startsWith("/Volumes/"))
        return set({ state: "error", error: "To get updates, drag Leafline Lead Finder into your Applications folder and open it from there." });
      try { fs.accessSync(path.dirname(where), fs.constants.W_OK); }
      catch (_) { return set({ state: "error", error: "Leafline can't update itself in its current folder. Move it into your Applications folder." }); }
      set({ state: "downloading", latest: info.version, percent: 0 });
      const dir = path.join(app.getPath("userData"), "pending-update"); fs.mkdirSync(dir, { recursive: true });
      const file = path.join(dir, path.basename(f.url));
      const dl = await fetch(`${base}/download/v${info.version}/${encodeURIComponent(f.url)}`);
      if (dl.status === 404) return building();
      if (!dl.ok || !dl.body) return set({ state: "error", error: `Couldn't download the update (GitHub answered ${dl.status}).` });
      const total = +dl.headers.get("content-length") || f.size || 0, hash = crypto.createHash("sha512"), out = fs.createWriteStream(file);
      let got = 0, last = 0;
      const reader = dl.body.getReader();
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          hash.update(value); got += value.length;
          if (!out.write(Buffer.from(value))) await new Promise((ok) => out.once("drain", ok));
          if (total && Date.now() - last > 250) { last = Date.now(); set({ state: "downloading", percent: Math.min(99, (got / total) * 100) }); }
        }
      } finally { await new Promise((ok) => out.end(ok)); }
      if (hash.digest("base64") !== f.sha512) {
        try { fs.unlinkSync(file); } catch (_) {}
        return set({ state: "error", error: "The downloaded update was damaged, so it wasn't installed. It will try again next time." });
      }
      mac.file = file; mac.version = info.version;
      set({ state: "ready", latest: info.version, percent: 100 });
    } catch (e) {
      set({ state: "error", error: "Couldn't update: " + String((e && e.message) || e).slice(0, 160) });
    } finally { mac.busy = null; }
  })();
  return mac.busy;
}

function macInstall() {
  if (!mac.file || installing) return;
  installing = true;
  writeGuard({ version: mac.version, at: Date.now(), from: app.getVersion() });
  try {
    const dir = path.dirname(mac.file), sh = path.join(dir, "install.sh");
    fs.writeFileSync(sh, require("./mac_update.js"), { mode: 0o755 });
    const { spawn } = require("child_process");
    spawn("/bin/bash", [sh, macAppPath(), mac.file, String(process.pid), dir], { detached: true, stdio: "ignore" }).unref();
    setImmediate(() => app.quit());
  } catch (e) { installing = false; set({ state: "error", error: "Couldn't restart to update: " + e.message }); }
}

// ---------------------------------------------------------------- both
function install() {
  if (MAC) return macInstall();
  if (!autoUpdater || installing) return;
  installing = true;
  writeGuard({ version: state.latest, at: Date.now(), from: app.getVersion() });
  setImmediate(() => { try { autoUpdater.quitAndInstall(true, true); } catch (e) { installing = false; set({ state: "error", error: "Couldn't restart to update: " + e.message }); } });
}

function check(onLaunch) {
  if (!MAC && !autoUpdater) { set({ state: "error", error: "Updates are not available in this copy of the app." }); return Promise.resolve(); }
  if (!app.isPackaged) { set({ state: "error", error: "Updates only work in the installed app, not when running from source." }); return Promise.resolve(); }
  if (!configured()) { set({ state: "error", error: "This build was made without an update address. Run SETUP_GITHUB.bat, then rebuild the installer once." }); return Promise.resolve(); }
  if (MAC) return macCheck();
  return autoUpdater.checkForUpdates().catch(() => {});
}

// the same version failed to install less than a day ago: don't loop, let the person decide in Settings
const failedBefore = (g, v) => g.version === v && Date.now() - (g.at || 0) < 86400000 && g.from === app.getVersion();

// Launch-time update: resolves true when the app is about to restart into the new version.
async function updateOnLaunch(timeoutMs = 20000) {
  if (!app.isPackaged || !configured() || (!MAC && !autoUpdater)) return false;
  const g = readGuard();
  if (MAC) {
    return new Promise((resolve) => {
      let done = false, t2 = null;
      const fin = (v) => { if (!done) { done = true; clearTimeout(t); clearTimeout(t2); resolve(v); } };
      // a download that started in time may take up to 10 minutes; otherwise the app opens and it finishes in the background
      const t = setTimeout(() => { if (state.state === "downloading") t2 = setTimeout(() => fin(false), 10 * 60 * 1000); else fin(false); }, timeoutMs);
      check(true).then(() => {
        if (state.state !== "ready" || failedBefore(g, state.latest)) return fin(false);
        if (done) return;                                       // the app already opened: Settings shows "Restart & update"
        fin(true); install();
      });
    });
  }
  return new Promise((resolve) => {
    let done = false;
    const fin = (v) => { if (!done) { done = true; clearTimeout(t); resolve(v); } };
    const t = setTimeout(() => fin(false), timeoutMs);
    autoUpdater.once("update-not-available", () => fin(false));
    autoUpdater.once("error", () => fin(false));
    autoUpdater.once("update-available", (i) => {
      if (failedBefore(g, i.version)) { clearTimeout(t); fin(false); return; }
      clearTimeout(t);
      autoUpdater.once("update-downloaded", () => { fin(true); install(); });
      setTimeout(() => fin(false), 10 * 60 * 1000);          // a very slow download never blocks the app for more than 10 minutes
    });
    check(true);
  });
}

module.exports = { init, check, install, updateOnLaunch, state, _mac: { parseMacYml, newer } };
