// Tests updater.js with fake "electron" and "electron-updater" modules (the real ones are installed on the PC at build time).
const Module = require("module"), path = require("path"), fs = require("fs"), os = require("os"), EventEmitter = require("events");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "upd-"));
let ok = 0, bad = 0; const check = (l, c) => { c ? (ok++, console.log("  PASS", l)) : (bad++, console.log("  FAIL", l)); };
function setup(opts) {
  const handlers = {}, sent = [];
  const au = new EventEmitter(); au.calls = []; au.installed = 0;
  au.checkForUpdates = async () => { au.calls.push("check"); setImmediate(() => opts.script(au)); };
  au.quitAndInstall = (silent, run) => { au.installed++; au.args = [silent, run]; };
  const ret = { quits: 0 };
  const electron = { app: { getVersion: () => "10.2.0", isPackaged: opts.packaged !== false, getPath: () => tmp, quit: () => { ret.quits++; } }, ipcMain: { handle: (n, f) => (handlers[n] = f) } };
  process.resourcesPath = opts.noYml ? path.join(tmp, "none") : tmp; if (!opts.noYml) fs.writeFileSync(path.join(tmp, "app-update.yml"), "provider: github\n");
  const orig = Module._load; Module._load = function (r, ...a) { if (r === "electron") return electron; if (r === "electron-updater") return { autoUpdater: au }; return orig.call(this, r, ...a); };
  delete require.cache[require.resolve("../updater.js")]; const U = require("../updater.js"); Module._load = orig;
  U.init(() => ({ isDestroyed: () => false, webContents: { send: (c, s) => sent.push(s) } }), () => {});
  return Object.assign(ret, { U, au, handlers, sent });
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
  console.log("Mac (its own updater: latest-mac.yml + .zip from GitHub)");
  const real = { platform: Object.getOwnPropertyDescriptor(process, "platform"), arch: Object.getOwnPropertyDescriptor(process, "arch"), execPath: process.execPath, fetch: global.fetch };
  const crypto = require("crypto"), cp = require("child_process"), realSpawn = cp.spawn;
  Object.defineProperty(process, "platform", { value: "darwin" }); Object.defineProperty(process, "arch", { value: "arm64" });
  const apps = path.join(tmp, "Applications"), bundle = path.join(apps, "Leafline Lead Finder.app");
  fs.mkdirSync(path.join(bundle, "Contents", "MacOS"), { recursive: true });
  process.execPath = path.join(bundle, "Contents", "MacOS", "Leafline Lead Finder");
  const ZIP = Buffer.from("PK fake zip " + "x".repeat(5000)), SHA = crypto.createHash("sha512").update(ZIP).digest("base64");
  const yml = (v, sha = SHA, a = "arm64") => `version: ${v}\nfiles:\n  - url: Leafline-Lead-Finder-${v}-${a}-mac.zip\n    sha512: ${sha}\n    size: ${ZIP.length}\n  - url: Leafline-Lead-Finder-${v}-${a}.dmg\n    sha512: abc\n    size: 9\npath: Leafline-Lead-Finder-${v}-${a}-mac.zip\nsha512: ${sha}\nreleaseDate: '2026-11-10T00:00:00.000Z'\n`;
  let G = {}, urls = [];
  global.fetch = async (u) => {
    urls.push(String(u));
    if (G.offline) throw new TypeError("fetch failed");
    if (/latest-mac-(arm64|x64)\.yml$/.test(u)) { G.list = String(u).match(/latest-mac-(\w+)\.yml$/)[1]; return G.yml === 404 ? new Response("Not Found", { status: 404 }) : new Response(G.yml, { status: 200 }); }
    if (/\.zip$/.test(u)) return G.zip === 404 ? new Response("Not Found", { status: 404 }) : new Response(G.zip || ZIP, { status: 200, headers: { "content-length": String((G.zip || ZIP).length) } });
    return new Response("?", { status: 500 });
  };
  const spawned = []; cp.spawn = (cmd, args, o) => { spawned.push({ cmd, args, o }); return { unref() {} }; };
  const macSetup = () => { const s = setup({ script: () => {} }); fs.writeFileSync(path.join(tmp, "app-update.yml"), "owner: LeaflineWebs\nrepo: leafline\nprovider: github\n"); return s; };
  const M = macSetup(); const { parseMacYml, newer } = M.U._mac;
  check("reads latest-mac.yml (version, zip, SHA-512)", parseMacYml(yml("10.3.0")).version === "10.3.0" && parseMacYml(yml("10.3.0")).files[0].sha512 === SHA);
  check("compares versions as numbers (10.10.0 is newer than 10.9.9)", newer("10.10.0", "10.9.9") && !newer("10.2.0", "10.2.0") && !newer("10.1.9", "10.2.0"));
  try { fs.unlinkSync(path.join(tmp, "update-attempt.json")); } catch (_) {}
  G = { yml: yml("10.2.0") }; urls = [];
  await M.handlers["update-check"]();
  check("same version online: 'You're on the latest version'", M.U.state.state === "none" && urls.length === 1 && /github\.com\/LeaflineWebs\/leafline\/releases\/latest\/download\/latest-mac-arm64\.yml$/.test(urls[0]));
  G = { yml: 404 }; await M.handlers["update-check"]();
  check("Mac files not online yet: 'still being built', not an error", M.U.state.state === "building");
  G = { offline: true }; await M.handlers["update-check"]();
  check("offline: a clear message", M.U.state.state === "error" && /internet/.test(M.U.state.error));
  G = { yml: yml("10.3.0", crypto.createHash("sha512").update("other").digest("base64")) }; await M.handlers["update-check"]();
  check("a damaged download is thrown away, not installed", M.U.state.state === "error" && /damaged/.test(M.U.state.error) && !fs.existsSync(path.join(tmp, "pending-update", "Leafline-Lead-Finder-10.3.0-arm64-mac.zip")));
  G = { yml: yml("10.3.0") }; urls = [];
  await M.handlers["update-check"]();
  const dl = path.join(tmp, "pending-update", "Leafline-Lead-Finder-10.3.0-arm64-mac.zip");
  check("a newer version downloads the Apple Silicon .zip from that release and checks it", M.U.state.state === "ready" && M.U.state.latest === "10.3.0" && fs.readFileSync(dl).equals(ZIP)
        && urls.some((u) => /\/releases\/download\/v10\.3\.0\/Leafline-Lead-Finder-10\.3\.0-arm64-mac\.zip$/.test(u)));
  check("progress was reported while downloading", M.sent.some((s) => s.state === "downloading"));
  // Restart & update
  await M.handlers["update-install"](); await new Promise((r) => setTimeout(r, 20));
  const sp = spawned[spawned.length - 1];
  check("Restart & update runs the swap script with the app, the download and this app's process id",
        sp && sp.cmd === "/bin/bash" && sp.args[1] === bundle && sp.args[2] === dl && sp.args[3] === String(process.pid) && sp.o.detached === true);
  check("...the script is written next to the download", fs.readFileSync(sp.args[0], "utf8") === require("../mac_update.js"));
  check("...and the app quits so the script can swap it", M.quits === 1);
  // launch-time: downloads and restarts straight away, like Windows
  try { fs.unlinkSync(path.join(tmp, "update-attempt.json")); } catch (_) {}
  const L = macSetup(); G = { yml: yml("10.4.0") }; const n0 = spawned.length;
  check("at launch a newer Mac version is downloaded and installed before the app opens", (await L.U.updateOnLaunch(3000)) === true && spawned.length === n0 + 1);
  const L2 = macSetup(); const n1 = spawned.length;
  check("if that same update failed to install, it doesn't loop at every launch", (await L2.U.updateOnLaunch(3000)) === false && spawned.length === n1);
  // not in Applications / Intel Mac
  process.execPath = "/private/var/folders/xy/T/AppTranslocation/ABC/d/Leafline Lead Finder.app/Contents/MacOS/Leafline Lead Finder";
  const T = macSetup(); G = { yml: yml("10.5.0") }; await T.handlers["update-check"]();
  check("run straight from Downloads (macOS 'translocation'): says to move it into Applications", T.U.state.state === "error" && /Applications/.test(T.U.state.error));
  process.execPath = path.join(bundle, "Contents", "MacOS", "Leafline Lead Finder");
  Object.defineProperty(process, "arch", { value: "x64" });
  const X = macSetup(); G = { yml: yml("10.5.0", SHA, "x64") }; urls = []; await X.handlers["update-check"]();
  check("an Intel Mac reads the Intel update list and downloads the Intel build", G.list === "x64" && X.U.state.state === "ready" && urls.some((u) => /Leafline-Lead-Finder-10\.5\.0-x64-mac\.zip$/.test(u)));
  G = { yml: yml("10.6.0") }; const X2 = macSetup(); await X2.handlers["update-check"]();
  check("...and never installs an Apple Silicon build by mistake", X2.U.state.state === "error");
  Object.defineProperty(process, "arch", real.arch);
  const S = setup({ packaged: false, script: () => {} }); await S.handlers["update-check"]();
  check("running from source on a Mac: the usual clear message", /installed app/.test(S.U.state.error));
  Object.defineProperty(process, "platform", real.platform); process.execPath = real.execPath; global.fetch = real.fetch; cp.spawn = realSpawn;
  console.log(`\n${ok} passed, ${bad} failed`); process.exit(bad ? 1 : 0);
})();
