"use strict";
const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const crypto = require("crypto");
const http = require("http");
const net = require("net");
const path = require("path");
const fs = require("fs");
const U = require("./updater");

let backend = null, win = null, quitting = false, spawnError = "", logFile = "";
const TOKEN = crypto.randomBytes(24).toString("hex");

if (!app.requestSingleInstanceLock()) app.quit();
app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });

function note(text) {
  // everything the engine prints goes to engine.log so a problem can always be found afterwards
  try {
    if (!logFile) { const dir = app.getPath("userData"); fs.mkdirSync(dir, { recursive: true }); logFile = path.join(dir, "engine.log"); }
    fs.appendFileSync(logFile, text);
  } catch (_) {}
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once("error", reject);
    s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => resolve(p)); });
  });
}

function backendCommand() {
  // Packaged app: PyInstaller build copied to resources/backend. Dev (npm start): run the Python file directly.
  const exe = process.platform === "win32" ? "leafline_backend.exe" : "leafline_backend";
  const packaged = path.join(process.resourcesPath || "", "backend", "leafline_backend", exe);
  if (app.isPackaged) return { cmd: packaged, args: [], missing: !fs.existsSync(packaged) };
  const py = process.platform === "win32" ? "python" : "python3";
  return { cmd: process.env.LEAFLINE_PYTHON || py, args: [path.join(__dirname, "backend", "leafline_backend.py")], missing: false };
}

function ping(port) {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port, path: "/ping?t=" + TOKEN, timeout: 800 }, (res) => { res.resume(); resolve(res.statusCode === 200); });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function waitReady(port, ms = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (spawnError || !backend || backend.exitCode !== null) return false;
    if (await ping(port)) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function hint() {
  return app.isPackaged ? "" :
    "\n\nRunning from source needs Python 3.10+ on your PATH and:  pip install requests playwright\n(or set LEAFLINE_PYTHON to your python.exe).";
}

async function startBackend() {
  const port = await freePort();
  const { cmd, args, missing } = backendCommand();
  let log = "";
  note(`\n--- ${new Date().toISOString()} starting engine: ${cmd} ${args.join(" ")} (port ${port})\n`);
  if (missing) throw new Error("The app engine file is missing from this install:\n" + cmd + "\n\nThe installer was built without the Python engine. Rebuild it (build_windows.bat / build_mac.sh) and reinstall.");
  backend = spawn(cmd, args, {
    env: { ...process.env, LEAFLINE_PORT: String(port), LEAFLINE_TOKEN: TOKEN, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
    windowsHide: true,
  });
  const keep = (b) => { const s = b.toString(); log = (log + s).slice(-4000); note(s.replace(/\?t=\S+/g, "?t=***")); };
  backend.stdout.on("data", keep);
  backend.stderr.on("data", keep);
  backend.on("error", (e) => { spawnError = e.message; log += "\n" + e.message; note("spawn error: " + e.message + "\n"); });
  backend.on("exit", (code) => {
    note(`engine exited (code ${code})\n`);
    if (!quitting && win) dialog.showErrorBox("Leafline Lead Finder", "The app engine stopped unexpectedly.\n\n" + log.slice(-1200) + "\n\nLog: " + logFile);
  });
  const ok = await waitReady(port);
  if (!ok) throw new Error("The app engine did not start.\n\n" + (spawnError || log || "No output from the engine.") + hint() + "\n\nLog file: " + logFile);
  return port;
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1480, height: 920, minWidth: 1180, minHeight: 740,
    backgroundColor: "#0F1A14", title: "Leafline Web Services - Lead Finder", show: false, autoHideMenuBar: true,
    icon: path.join(__dirname, "build", "icon.png"),
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.once("ready-to-show", () => win.show());
  win.on("closed", () => { win = null; });
  // links that leave the app open in the normal browser
  win.webContents.setWindowOpenHandler(({ url }) => { if (/^(https?|mailto):/i.test(url)) shell.openExternal(url); return { action: "deny" }; });   // web links open in the browser, email links in the email app
  // show something right away: the engine can take several seconds on the very first start
  win.show();
  win.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(
    '<body style="margin:0;background:#0F1A14;color:#EEF7F0;font:600 16px Segoe UI,system-ui,sans-serif;display:grid;place-items:center;height:100vh">Starting Leafline Lead Finder...</body>')).catch(() => {});
  U.init(() => win, note);
  const splash = (t) => { try { if (win && !win.isDestroyed() && !win.webContents.getURL().startsWith("http://127.0.0.1")) win.webContents.executeJavaScript("document.body.innerText=" + JSON.stringify(t)).catch(() => {}); } catch (_) {} };
  const onStatus = (s) => { if (s.state === "downloading") splash("Downloading update " + (s.latest || "") + (s.percent ? " (" + Math.round(s.percent) + "%)" : "...")); else if (s.state === "ready") splash("Installing update " + (s.latest || "") + "..."); };
  const poll = setInterval(() => onStatus(U.state), 400);
  const upd = U.updateOnLaunch();                       // looks for a newer version while the engine starts
  let port;
  try { port = await startBackend(); } finally { /* keep the update check running either way */ }
  if (await upd) { return; }                            // an update was downloaded: the app is restarting into it
  clearInterval(poll);
  win.webContents.on("will-navigate", (e, url) => { if (!url.startsWith("http://127.0.0.1:" + port)) { e.preventDefault(); if (/^(https?|mailto):/i.test(url)) shell.openExternal(url); } });
  await win.loadURL(`http://127.0.0.1:${port}/?t=${TOKEN}`);
  setInterval(() => { if (U.state.state !== "downloading" && U.state.state !== "ready") U.check(false); }, 4 * 3600 * 1000);   // long-running sessions
}

ipcMain.handle("save-csv", async (_e, name) => {
  const r = await dialog.showSaveDialog(win, {
    defaultPath: path.join(app.getPath("documents"), String(name).replace(/[^\w.\- ]/g, "_")),
    filters: [{ name: "CSV files", extensions: ["csv"] }],
  });
  return r.canceled ? "" : r.filePath;
});

// Invoice PDFs (11.15): the page makes the PDF; this asks where to save it and writes it. Only real PDFs, at most 20 MB.
ipcMain.handle("save-pdf", async (_e, name, bytes) => {
  const buf = Buffer.from(bytes instanceof Uint8Array ? bytes : new Uint8Array(0));
  if (buf.length < 8 || buf.length > 20 * 1024 * 1024 || buf.subarray(0, 5).toString("latin1") !== "%PDF-") return { ok: false, error: "That isn't a PDF." };
  const r = await dialog.showSaveDialog(win, {
    defaultPath: path.join(app.getPath("documents"), String(name).replace(/[^\w.\- ]/g, "_").replace(/\.pdf$/i, "") + ".pdf"),
    filters: [{ name: "PDF files", extensions: ["pdf"] }],
  });
  if (r.canceled || !r.filePath) return { ok: false, canceled: true };
  const fp = /\.pdf$/i.test(r.filePath) ? r.filePath : r.filePath + ".pdf";
  try { await fs.promises.writeFile(fp, buf); } catch (e) { return { ok: false, error: e.message }; }
  return { ok: true, path: fp };
});

function stopBackend() {
  quitting = true;
  if (backend && backend.exitCode === null && backend.pid) {
    try {
      if (process.platform === "win32") spawn("taskkill", ["/pid", String(backend.pid), "/T", "/F"], { windowsHide: true });
      else backend.kill("SIGTERM");
    } catch (_) {}
  }
}

process.on("uncaughtException", (e) => { note("uncaught: " + (e && e.stack || e) + "\n"); });
app.whenReady().then(() => createWindow().catch((e) => { note("fatal: " + e.message + "\n"); dialog.showErrorBox("Leafline Lead Finder", e.message); app.quit(); }));
app.on("window-all-closed", () => app.quit());
app.on("before-quit", stopBackend);
app.on("will-quit", stopBackend);
