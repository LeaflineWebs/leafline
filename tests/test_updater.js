// Tests updater.js with fake "electron" and "electron-updater" modules (the real ones are installed on the PC at build time).
const Module = require("module"), path = require("path"), fs = require("fs"), os = require("os"), EventEmitter = require("events");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "upd-"));
let ok = 0, bad = 0; const check = (l, c) => { c ? (ok++, console.log("  PASS", l)) : (bad++, console.log("  FAIL", l)); };
function setup(opts) {
  const handlers = {}, sent = [];
  const au = new EventEmitter(); au.calls = []; au.installed = 0;
  au.checkForUpdates = async () => { au.calls.push("check"); setImmediate(() => opts.script(au)); };
  au.quitAndInstall = (silent, run) => { au.installed++; au.args = [silent, run]; };
  const electron = { app: { getVersion: () => "10.2.0", isPackaged: opts.packaged !== false, getPath: () => tmp }, ipcMain: { handle: (n, f) => (handlers[n] = f) } };
  process.resourcesPath = opts.noYml ? path.join(tmp, "none") : tmp; if (!opts.noYml) fs.writeFileSync(path.join(tmp, "app-update.yml"), "provider: github\n");
  const orig = Module._load; Module._load = function (r, ...a) { if (r === "electron") return electron; if (r === "electron-updater") return { autoUpdater: au }; return orig.call(this, r, ...a); };
  delete require.cache[require.resolve("../updater.js")]; const U = require("../updater.js"); Module._load = orig;
  U.init(() => ({ isDestroyed: () => false, webContents: { send: (c, s) => sent.push(s) } }), () => {});
  return { U, au, handlers, sent };
}
(async () => {
  try { fs.unlinkSync(path.join(tmp, "update-attempt.json")); } catch (_) {}
  console.log("up to date");
  let t = setup({ script: (au) => au.emit("update-not-available", {}) });
  check("launch check finds nothing -> app opens normally", (await t.U.updateOnLaunch(3000)) === false && t.au.installed === 0);
  console.log("new version");
  t = setup({ script: (au) => { au.emit("update-available", { version: "10.3.0" }); au.emit("download-progress", { percent: 40 }); setTimeout(() => au.emit("update-downloaded", { version: "10.3.0" }), 20); } });
  check("launch check downloads and installs silently", (await t.U.updateOnLaunch(3000)) === true);
  await new Promise((r) => setTimeout(r, 30));
  check("installer started once, silent, and runs the app afterwards", t.au.installed === 1 && t.au.args[0] === true && t.au.args[1] === true);
  check("the page was told about progress and readiness", t.sent.some((s) => s.state === "downloading" && s.percent === 40) && t.sent.some((s) => s.state === "ready" && s.latest === "10.3.0"));
  console.log("same update failed before (loop guard)");
  t = setup({ script: (au) => au.emit("update-available", { version: "10.3.0" }) });
  check("does not retry the same update at every launch", (await t.U.updateOnLaunch(3000)) === false && t.au.installed === 0);
  console.log("offline / error");
  t = setup({ script: (au) => au.emit("error", new Error("net::ERR_INTERNET_DISCONNECTED")) });
  check("update check error never blocks the app", (await t.U.updateOnLaunch(3000)) === false);
  check("error is shown in settings in plain words", t.U.state.state === "error" && /Couldn't update/.test(t.U.state.error));
  t = setup({ script: (au) => au.emit("error", new Error('Cannot find latest.yml in the latest release artifacts (https://github.com/x/y/releases/download/v11.2.2/latest.yml): HttpError: 404')) });
  check("new version still building online: calm message, not an error", (await t.U.updateOnLaunch(3000)) === false && t.U.state.state === "building" && !t.U.state.error);
  console.log("settings button");
  t = setup({ script: (au) => au.emit("update-not-available", {}) });
  const r = await t.handlers["update-check"](); await new Promise((r) => setTimeout(r, 20));
  check("Check for updates reports 'none' when current", t.U.state.state === "none");
  check("app-info returns the version", (await t.handlers["app-info"]()).version === "10.2.0");
  t = setup({ script: (au) => { au.emit("update-available", { version: "10.4.0" }); au.emit("update-downloaded", { version: "10.4.0" }); } });
  await t.handlers["update-check"](); await new Promise((r) => setTimeout(r, 20));
  check("button flow: ready state then Restart installs", t.U.state.state === "ready"); await t.handlers["update-install"](); await new Promise((r) => setTimeout(r, 20)); check("restart button installs the update", t.au.installed === 1);
  console.log("not packaged / not configured");
  t = setup({ packaged: false, script: () => {} });
  check("running from source: clear message, no network", (await t.U.updateOnLaunch(500)) === false && t.au.calls.length === 0);
  await t.handlers["update-check"](); check("source run explains why", /installed app/.test(t.U.state.error));
  t = setup({ noYml: true, script: () => {} }); await t.handlers["update-check"](); check("no update address built in: tells you what to do", /SETUP_GITHUB/.test(t.U.state.error) && t.au.calls.length === 0);
  console.log(`\n${ok} passed, ${bad} failed`); process.exit(bad ? 1 : 0);
})();
