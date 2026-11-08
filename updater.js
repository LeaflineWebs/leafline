"use strict";
// Automatic updates for the desktop app (electron-updater + GitHub Releases).
// On launch: look for a newer version; if there is one, download it and install it right away (before the app opens),
// unless that same update already failed once. While the app is open: "Check for updates" in Account & Settings.
const { app, ipcMain } = require("electron");
const fs = require("fs");
const path = require("path");

let autoUpdater = null, loadError = "";
try { ({ autoUpdater } = require("electron-updater")); } catch (e) { loadError = e.message; }

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
    if (/latest\.yml|404|HttpError: 404/i.test(msg)) {
      set({ state: "building", error: "" });
      clearTimeout(retryT); retryT = setTimeout(() => check(true), 5 * 60 * 1000);
      return;
    }
    set({ state: "error", error: "Couldn't update: " + msg.slice(0, 160) });
  });
}

function install() {
  if (!autoUpdater || installing) return;
  installing = true;
  writeGuard({ version: state.latest, at: Date.now(), from: app.getVersion() });
  setImmediate(() => { try { autoUpdater.quitAndInstall(true, true); } catch (e) { installing = false; set({ state: "error", error: "Couldn't restart to update: " + e.message }); } });
}

function check(onLaunch) {
  if (!autoUpdater) { set({ state: "error", error: "Updates are not available in this copy of the app." }); return Promise.resolve(); }
  if (!app.isPackaged) { set({ state: "error", error: "Updates only work in the installed app, not when running from source." }); return Promise.resolve(); }
  if (!configured()) { set({ state: "error", error: "This build was made without an update address. Run SETUP_GITHUB.bat, then rebuild the installer once." }); return Promise.resolve(); }
  return autoUpdater.checkForUpdates().catch(() => {});
}

// Launch-time update: resolves true when the app is about to restart into the new version.
async function updateOnLaunch(timeoutMs = 20000) {
  if (!autoUpdater || !app.isPackaged || !configured()) return false;
  const g = readGuard();
  return new Promise((resolve) => {
    let done = false;
    const fin = (v) => { if (!done) { done = true; clearTimeout(t); resolve(v); } };
    const t = setTimeout(() => fin(false), timeoutMs);
    autoUpdater.once("update-not-available", () => fin(false));
    autoUpdater.once("error", () => fin(false));
    autoUpdater.once("update-available", (i) => {
      // the same version failed to install less than a day ago: don't loop, let the person decide in Settings
      if (g.version === i.version && Date.now() - (g.at || 0) < 86400000 && g.from === app.getVersion()) { clearTimeout(t); fin(false); return; }
      clearTimeout(t);
      autoUpdater.once("update-downloaded", () => { fin(true); install(); });
      setTimeout(() => fin(false), 10 * 60 * 1000);          // a very slow download never blocks the app for more than 10 minutes
    });
    check(true);
  });
}

module.exports = { init, check, install, updateOnLaunch, state };
