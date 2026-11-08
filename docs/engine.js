/* Leafline web engine: the same API the desktop app's Python engine offers, talking straight to Supabase.
   Only the PUBLISHABLE key lives here (public by design; row level security protects the data). */
"use strict";
(function () {
  const C = window.LF_CONFIG || {};
  const SB = String(C.url || "").replace(/\/+$/, ""), KEY = C.key || "", VERSION = String(C.version || "0"), BUILD = String(C.build || C.version || "0");
  const TZ = "America/Toronto", DOMAIN = "leaflineweb.com", NA = "N/A";
  const NS = "6f1e3d8a-5b0c-4c7e-9a52-1d3a7c0b9e11";
  const SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const STATUS = ["none", "green", "yellow", "orange", "red"];
  const OUTCOME = { orange: "no_answer", red: "not_interested", yellow: "interested", green: "meeting_booked" };
  const OUTCOMES = ["no_answer", "voicemail", "interested", "not_interested", "follow_up", "meeting_booked", "sale_completed"];
  const REPEATS = ["none", "daily", "weekly", "monthly", "yearly"];
  const EVENT_COLORS = ["#3DDC84", "#4DD0E1", "#5C9DFF", "#B388FF", "#FF7EB6", "#FF5C5C", "#FF9F43", "#FFD60A", "#C6F04A", "#B8C4BC"];
  const EVENT_ICONS = ["cal", "users", "phone", "video", "coffee", "briefcase", "dollar", "gift", "star", "flag", "heart", "bolt", "pin", "mail", "clock", "trophy", "bell", "check"];
  const COLORS = ["#3DDC84", "#5EE6B8", "#FFD60A", "#FF9F43", "#F2788A", "#7FB6FF"];
  const PEXT = ["title", "bio", "thought", "thought_at", "mood", "accent"];
  const MEDIA = ["avatar_url", "banner_url", "banner_pos"];
  const LS = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { } },
  };
  class Offline extends Error { }
  class AuthLost extends Error { }
  class AuthFail extends Error { }
  class Http extends Error { constructor(status, body) { super(typeof body === "string" ? body : JSON.stringify(body || {})); this.status = status; this.body = body; this.code = body && body.code; } }

  // ------------------------------------------------------------------ time (the company works in Toronto time)
  const pad = (n) => String(n).padStart(2, "0");
  const dtf = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  function parts(d) { const o = {}; dtf.formatToParts(d).forEach((x) => (o[x.type] = x.value)); if (o.hour === "24") o.hour = "00"; return o; }
  function nowLocal(d) { const o = parts(d || new Date()); return `${o.year}-${o.month}-${o.day} ${o.hour}:${o.minute}`; }
  function todayStr() { return nowLocal().slice(0, 10); }
  function isoToLocal(iso) { if (!iso) return ""; const d = new Date(iso); return isNaN(d) ? "" : nowLocal(d); }
  function localToISO(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(s || "").trim());
    if (!m) return null;
    const [y, mo, d, h, mi] = m.slice(1).map(Number), want = Date.UTC(y, mo - 1, d, h, mi);
    let t = want;
    for (let i = 0; i < 3; i++) { const o = parts(new Date(t)); const got = Date.UTC(+o.year, +o.month - 1, +o.day, +o.hour, +o.minute); const diff = want - got; if (!diff) break; t += diff; }
    return new Date(t).toISOString();
  }
  const nowIso = () => new Date().toISOString();
  // calendar days are UTC-midnight Date objects
  function parseDay(v) { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v || "").trim()); if (!m) return null; const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])); return d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3] ? d : null; }
  const dayStr = (d) => d.toISOString().slice(0, 10);
  const addDays = (d, n) => new Date(d.getTime() + n * 86400000);
  const wd = (d) => (d.getUTCDay() + 6) % 7;                 // Monday = 0
  const dim = (y, m) => new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  function addMonths(d, n, anchor) { const t = d.getUTCFullYear() * 12 + d.getUTCMonth() + n, y = Math.floor(t / 12), m = t % 12; return new Date(Date.UTC(y, m, Math.min(anchor, dim(y, m)))); }
  const money = (x) => Math.round(Number(x) * 100) / 100;
  const num = (x) => money(x || 0);
  const digits10 = (p) => String(p || "").replace(/\D/g, "").slice(-10);

  // ------------------------------------------------------------------ opening hours -> "open now?"
  const T = "\\d{1,2}(?::\\d{2})?\\s*(?:[ap]\\.?m\\.?)?";
  const RANGE = new RegExp("(" + T + ")\\s*-\\s*(" + T + ")", "g");
  function tok(s) { const m = /^\s*(\d{1,2})(?::(\d{2}))?\s*([ap])?/.exec(s); return [+m[1], +(m[2] || 0), m[3] || ""]; }
  function mins(h, m, ap) { if (ap) h = (h % 12) + (ap === "p" ? 12 : 0); return h * 60 + m; }
  function normHours(txt) {
    let t = String(txt || "").replace(/[    ]/g, " ").replace(/[–—‒]/g, "-");
    t = t.replace(/\s+(?:to|until)\s+/gi, "-");
    return t.replace(/\s+/g, " ").trim();
  }
  function parseRanges(txt) {
    const t = normHours(txt).toLowerCase();
    if (t.includes("24 hours") || t.includes("open 24")) return [[0, 1440]];
    const out = []; let m; RANGE.lastIndex = 0;
    while ((m = RANGE.exec(t))) {
      const [h1, m1, ap1] = tok(m[1]), [h2, m2, ap2] = tok(m[2]);
      const end0 = mins(h2, m2, ap2); let start = mins(h1, m1, ap1 || ap2), end = end0;
      if (!ap1 && ap2 && start > end) start -= 720;
      if (end <= start) end += 1440;
      out.push([start, end]);
    }
    return out;
  }
  function fmtMin(m) { m = ((m % 1440) + 1440) % 1440; const h = Math.floor(m / 60), mm = m % 60, ap = h < 12 ? "am" : "pm"; return mm ? `${h % 12 || 12}:${pad(mm)} ${ap}` : `${h % 12 || 12} ${ap}`; }
  function openStatus(hoursJson) {
    let h = {}; try { h = hoursJson ? JSON.parse(hoursJson) : {}; } catch (e) { h = {}; }
    const now = nowLocal(), nd = parseDay(now), idx = wd(nd), nowM = +now.slice(11, 13) * 60 + +now.slice(14, 16);
    const today = h && typeof h === "object" ? h[DAYS[idx]] : null;
    if (!today) return ["unknown", NA, ""];
    const ranges = parseRanges(today), closedWord = today.toLowerCase().includes("closed") && !ranges.length;
    let label = closedWord ? "Closed" : ranges.length ? normHours(today).replace(/-/g, "–") : normHours(today);
    if (!ranges.length && !closedWord) return ["unknown", label, ""];
    const prev = h[DAYS[(idx + 6) % 7]] || "";
    const spill = parseRanges(prev).filter((r) => r[1] > 1440).map((r) => r[1] - 1440);
    const left = ranges.filter((r) => r[0] <= nowM && nowM < r[1]).map((r) => r[1] - nowM).concat(spill.filter((s) => nowM < s).map((s) => s - nowM));
    if (left.length) {
      if (closedWord && spill.length) label = "Until " + fmtMin(Math.max(...spill));
      const m = Math.min(...left);
      return ["open", label, m <= 60 ? `Closes in ${m} min` : ""];
    }
    const later = ranges.filter((r) => r[0] > nowM).map((r) => r[0]);
    return ["closed", label, later.length ? `Opens ${fmtMin(Math.min(...later))}` : ""];
  }

  // ------------------------------------------------------------------ ids: the page wants numbers, the database uses uuids
  const byLid = { deals: new Map(), events: new Map(), notes: new Map() };
  function lidOf(t, uuid) {
    let n = parseInt(String(uuid).replace(/-/g, "").slice(0, 12), 16);
    for (let i = 0; i < 50; i++, n++) { const cur = byLid[t].get(n); if (cur === undefined || cur === uuid) { byLid[t].set(n, uuid); return n; } }
    return n;
  }
  const uuid4 = () => (crypto.randomUUID ? crypto.randomUUID() : "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)));
  async function uuid5(name) {
    const ns = NS.replace(/-/g, "").match(/../g).map((h) => parseInt(h, 16)), nm = new TextEncoder().encode(name);
    const buf = new Uint8Array(ns.length + nm.length); buf.set(ns); buf.set(nm, ns.length);
    const h = new Uint8Array(await crypto.subtle.digest("SHA-1", buf)).slice(0, 16);
    h[6] = (h[6] & 0x0f) | 0x50; h[8] = (h[8] & 0x3f) | 0x80;
    const x = Array.from(h, (b) => pad2(b)).join("");
    return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
  }
  const pad2 = (b) => b.toString(16).padStart(2, "0");

  // ------------------------------------------------------------------ state
  const st = {
    session: LS.get("lf_session", null), me: LS.get("lf_me", null), profile: null,
    leads: new Map(), deals: new Map(), events: new Map(), notes: new Map(), people: LS.get("lf_people", []),
    caps: { done: null, avatar: null, pext: null, media: null, paid: null }, prefs: LS.get("lf_prefs", {}), cosmetic: LS.get("lf_profile", null),
    sync: { state: "signed_out", pending: 0, blocked: 0, conflicts: 0, last_ok: null, error: "" },
    since: {}, lastBeat: 0, lastRecon: 0, loaded: false, busy: false, cycle: 0, teamCache: LS.get("lf_team", null), callsCache: LS.get("lf_calls", null),
  };
  const emit = (e, d) => { try { if (window.onPy) window.onPy({ e, d: d || {} }); } catch (x) { console.error(x); } };
  const uid = () => (st.session && st.session.uid) || "";
  function setSync(state, err) {
    const out = LS.get("lf_outbox", []);
    st.sync = { state, pending: out.filter((o) => !o.blocked).length, blocked: out.filter((o) => o.blocked).length, conflicts: 0, last_ok: state === "synced" ? new Date().toLocaleTimeString() : st.sync.last_ok, error: err || "" };
    emit("sync", st.sync);
  }

  // ------------------------------------------------------------------ http
  async function authPost(grant, body) {
    let r;
    try { r = await fetch(`${SB}/auth/v1/token?grant_type=${grant}`, { method: "POST", headers: { apikey: KEY, "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
    catch (e) { throw new Offline(String(e)); }
    return r;
  }
  function takeSession(j) { st.session = { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Math.floor(Date.now() / 1000) + (j.expires_in || 3600), uid: (j.user && j.user.id) || (st.session && st.session.uid) || "" }; LS.set("lf_session", st.session); }
  let refreshing = null;
  function refresh() {
    if (!st.session) throw new AuthLost();
    if (!refreshing) refreshing = (async () => {
      try {
        const r = await authPost("refresh_token", { refresh_token: st.session.refresh_token });
        if ([400, 401, 403].includes(r.status)) throw new AuthLost();
        if (!r.ok) throw new Http(r.status, await r.text());
        takeSession(await r.json());
      } finally { refreshing = null; }
    })();
    return refreshing;
  }
  async function token() {
    if (!st.session) throw new AuthLost();
    if (st.session.expires_at - 60 < Date.now() / 1000) await refresh();
    return st.session.access_token;
  }
  async function call(method, path, { params, body, prefer, retry = true } = {}) {
    const h = { apikey: KEY, Authorization: "Bearer " + (await token()), "Content-Type": "application/json" };
    if (prefer) h.Prefer = prefer;
    const q = params ? "?" + new URLSearchParams(params).toString() : "";
    let r;
    try { r = await fetch(SB + path + q, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) }); }
    catch (e) { throw new Offline(String(e)); }
    if (r.status === 401 && retry) { await refresh(); return call(method, path, { params, body, prefer, retry: false }); }
    const txt = await r.text();
    let j = []; try { j = txt ? JSON.parse(txt) : []; } catch (e) { j = txt; }
    if (r.status >= 400) throw new Http(r.status, j);
    return j;
  }
  const rest = (method, table, o) => call(method, "/rest/v1/" + table, o);
  async function allPages(table, params, page = 1000) {
    const out = []; let off = 0;
    for (;;) { const rows = await rest("GET", table, { params: { ...params, limit: page, offset: off } }); out.push(...rows); if (rows.length < page) return out; off += page; }
  }

  // ------------------------------------------------------------------ remote row <-> local row
  const leadIn = (R) => ({
    id: R.id, name: R.name || "", phone: R.phone || "", owner: R.owner_name || NA, rating: R.rating || NA, reviews: R.reviews || NA, website: R.website || NA,
    address: R.address || NA, search: R.search || "", btype: R.btype || "", hours: R.hours || "", status: R.status || "none", notes: R.notes || "",
    enriched: R.enriched ? 1 : 0, added_at: isoToLocal(R.added_at), called_at: isoToLocal(R.called_at), meeting_at: isoToLocal(R.meeting_at), called_by: R.called_by || "", version: R.version || 1,
  });
  const dealIn = (R) => ({ uuid: R.id, id: lidOf("deals", R.id), client: R.client || "", upfront: Number(R.upfront || 0), monthly: Number(R.monthly || 0), months: R.months || 0, closed_at: R.closed_at || "", first_bill: R.first_bill || R.closed_at || "", notes: R.notes || "", confirmed: R.confirmed || "", created_at: R.created_at || "" });
  const eventIn = (R) => ({
    uuid: R.id, id: lidOf("events", R.id), title: R.title || "", date: R.day || "", time: R.start_time || "", color: R.color || EVENT_COLORS[0], icon: R.icon || EVENT_ICONS[0],
    repeat: R.repeat_kind || "none", until: R.until || "", notes: R.notes || "", lead_id: R.lead_id || "", assigned_to: R.assigned_to || "", created_by: R.created_by || "",
    done: !!R.done, done_at: R.done_at || "",
  });
  const noteIn = (R) => ({ uuid: R.id, id: lidOf("notes", R.id), kind: R.kind || "note", scope: R.scope || "personal", title: R.title || "Untitled", folder: R.folder || "", body: R.body || "", owner_id: R.owner_id || "", created_at: R.created_at || "" });
  const TABLES = { leads: leadIn, deals: dealIn, events: eventIn, notes: noteIn };
  const mapOf = (t) => st[t];
  const keyOf = (t, row) => (t === "leads" ? row.id : row.uuid);

  // ------------------------------------------------------------------ cache (instant start, works offline)
  const IDB = {
    db: null,
    open() { return this.db || (this.db = new Promise((res, rej) => { try { const r = indexedDB.open("leafline", 1); r.onupgradeneeded = () => r.result.createObjectStore("kv"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); } catch (e) { rej(e); } })); },
    async get(k) { try { const d = await this.open(); return await new Promise((res, rej) => { const q = d.transaction("kv").objectStore("kv").get(k); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); }); } catch (e) { return undefined; } },
    async put(k, v) { try { const d = await this.open(); await new Promise((res, rej) => { const t = d.transaction("kv", "readwrite"); t.objectStore("kv").put(v, k); t.oncomplete = res; t.onerror = () => rej(t.error); }); } catch (e) { } },
    async del(k) { try { const d = await this.open(); await new Promise((res) => { const t = d.transaction("kv", "readwrite"); t.objectStore("kv").delete(k); t.oncomplete = res; t.onerror = res; }); } catch (e) { } },
  };
  let saveT = null;
  function saveCache() {
    clearTimeout(saveT);
    saveT = setTimeout(() => { if (!uid()) return; IDB.put("snap", { uid: uid(), leads: [...st.leads.values()], deals: [...st.deals.values()], events: [...st.events.values()], notes: [...st.notes.values()], since: st.since }); }, 1500);
  }
  async function loadCache() {
    const s = await IDB.get("snap");
    if (!s || s.uid !== uid()) return false;
    st.leads = new Map(s.leads.map((r) => [r.id, r]));
    for (const t of ["deals", "events", "notes"]) { st[t] = new Map(); for (const r of s[t]) { byLid[t].set(r.id, r.uuid); st[t].set(r.uuid, r); } }
    st.since = s.since || {}; st.loaded = true;
    return true;
  }
  function clearData() {
    st.leads = new Map(); st.deals = new Map(); st.events = new Map(); st.notes = new Map(); st.since = {}; st.loaded = false; st.teamCache = null; st.callsCache = null;
    ["lf_team", "lf_calls", "lf_outbox"].forEach(LS.del); IDB.del("snap");
  }

  // ------------------------------------------------------------------ outbox: every change is kept on this device until the server has it
  let flushing = false;
  function enqueue(op) { const q = LS.get("lf_outbox", []); q.push({ ...op, qid: uuid4(), actor: uid(), at: Date.now() }); LS.set("lf_outbox", q); setSync(st.sync.state === "offline" ? "offline" : "syncing"); flush(); }
  async function runOp(o) {
    if (o.kind === "patch") return rest("PATCH", o.table, { params: { id: "eq." + o.id }, body: o.body, prefer: "return=minimal" });
    if (o.kind === "insert") return rest("POST", o.table, { params: { on_conflict: o.conflict || "id" }, body: o.body, prefer: "resolution=ignore-duplicates,return=minimal" });
    if (o.kind === "delete") return rest("DELETE", o.table, { params: { id: "eq." + o.id }, prefer: "return=minimal" });
    if (o.kind === "settings") return rest("POST", "settings", { params: { on_conflict: "key" }, body: o.body, prefer: "resolution=merge-duplicates,return=minimal" });
    throw new Error("unknown op");
  }
  async function flush() {
    if (flushing || !uid()) return;
    flushing = true;
    try {
      for (;;) {
        const q = LS.get("lf_outbox", []), o = q.find((x) => !x.blocked && (!x.actor || x.actor === uid()));
        if (!o) break;
        try { await runOp(o); LS.set("lf_outbox", LS.get("lf_outbox", []).filter((x) => x.qid !== o.qid)); }
        catch (e) {
          if (e instanceof Offline) { setSync("offline", "No connection"); return; }
          if (e instanceof AuthLost) { onAuthLost(); return; }
          const transient = e instanceof Http && ([408, 425, 429, 500, 502, 503, 504].includes(e.status) || e.code === "23503");
          if (transient) { setSync("error", String(e.message).slice(0, 160)); return; }
          LS.set("lf_outbox", LS.get("lf_outbox", []).map((x) => (x.qid === o.qid ? { ...x, blocked: true, error: String(e.message).slice(0, 200) } : x)));
        }
      }
      setSync(LS.get("lf_outbox", []).some((x) => x.blocked) ? "attention" : "synced");
    } finally { flushing = false; }
  }
  const pendingCount = () => LS.get("lf_outbox", []).filter((x) => !x.blocked).length;

  // ------------------------------------------------------------------ sign in / profile
  async function probe(col, table, key) {
    try { await rest("GET", table, { params: { select: col, limit: 1 } }); st.caps[key] = true; }
    catch (e) { if (e instanceof Http && [400, 404].includes(e.status)) st.caps[key] = false; else throw e; }
  }
  async function probeAll() {
    for (const [col, table, key] of [["done,done_at", "events", "done"], ["avatar", "profiles", "avatar"], ["bio,thought,thought_at,title,mood,accent,banner", "profiles", "pext"], ["avatar_url,banner_url,banner_pos", "profiles", "media"], ["confirmed", "deals", "paid"]]) {
      if (st.caps[key] == null) { try { await probe(col, table, key); } catch (e) { if (e instanceof Offline || e instanceof AuthLost) throw e; } }
    }
  }
  const pcols = (base) => base + (st.caps.avatar ? ",avatar" : "") + (st.caps.pext ? "," + PEXT.join(",") : "") + (st.caps.media ? "," + MEDIA.join(",") : "");
  const mediaOf = () => ({ avatar_url: "", banner_url: "", banner_pos: 50, ...LS.get("lf_media", {}) });
  const pub = (p) => ({ id: p.id, name: p.display_name || p.username, role: p.role, avatar: p.avatar || "", ext: Object.fromEntries(PEXT.map((k) => [k, p[k] || ""])), media: Object.fromEntries(MEDIA.filter((k) => p[k] != null).map((k) => [k, p[k]])) });
  function meOf() {
    if (!st.session) return null;
    const p = st.profile || {}, c = st.me || {};
    const ext = LS.get("lf_ext", null) || {};
    const o = { id: p.id || c.id || uid(), username: p.username || c.username, display_name: p.display_name || c.display_name, role: p.role || c.role, must_change_password: p.must_change_password != null ? p.must_change_password : c.must_change_password };
    if (!o.username) return null;
    o.avatar = LS.get("lf_avatar", "") || "";
    o.ext = { ...Object.fromEntries(PEXT.map((k) => [k, ""])), ...ext, banner: LS.get("lf_banner", "") || "" };
    o.media = mediaOf();
    return o;
  }
  function cacheMe() { const m = meOf(); if (m) { st.me = { id: m.id, username: m.username, display_name: m.display_name, role: m.role, must_change_password: m.must_change_password }; LS.set("lf_me", st.me); } }
  async function fetchProfile() {
    const rows = await rest("GET", "profiles", { params: { id: "eq." + uid(), select: "*" } });
    if (!rows.length) throw new AuthFail("No Leafline profile exists for this login. Ask an administrator.");
    const R = rows[0]; st.profile = R;
    if ("avatar" in R && !LS.get("lf_avatar_pending", false)) LS.set("lf_avatar", R.avatar || "");
    if ("bio" in R && !LS.get("lf_ext_pending", false)) { LS.set("lf_ext", Object.fromEntries(PEXT.map((k) => [k, R[k] || ""]))); LS.set("lf_banner", R.banner || ""); }
    if ("avatar_url" in R) LS.set("lf_media", Object.fromEntries(MEDIA.map((k) => [k, R[k]])));
    cacheMe();
    return R;
  }
  async function signIn(username, password) {
    const r = await authPost("password", { email: `${String(username).trim().toLowerCase()}@${DOMAIN}`, password });
    if ([400, 401, 403, 422].includes(r.status)) throw new AuthFail("Wrong username or password.");
    if (!r.ok) throw new Http(r.status, await r.text());
    const prevUid = uid();
    takeSession(await r.json());
    if (prevUid && prevUid !== uid()) { clearData(); }
    let prof;
    try { prof = await fetchProfile(); } catch (e) { LS.del("lf_session"); st.session = null; throw e; }
    if (!prof.active) { LS.del("lf_session"); st.session = null; throw new AuthFail("This account has been deactivated. Ask an administrator."); }
    const other = LS.get("lf_outbox", []).some((o) => o.actor && o.actor !== uid());
    if (other && prof.role !== "admin") { LS.del("lf_session"); st.session = null; throw new AuthFail("This device still holds unsynced changes made by another employee. They must sign in and finish syncing first."); }
    startLoop(true);
    return meOf();
  }
  function onAuthLost(why) {
    LS.del("lf_session"); LS.del("lf_me"); st.session = null; st.profile = null; st.me = null; st.loaded = false;
    ["lf_avatar", "lf_avatar_pending", "lf_ext", "lf_banner", "lf_ext_pending"].forEach(LS.del);
    setSync("signed_out"); emit("auth_lost", why ? { why } : {});
  }

  // ------------------------------------------------------------------ pulling
  async function pullTable(t) {
    const params = { select: "*", order: "updated_at.asc" };
    if (st.since[t]) params["updated_at"] = "gt." + st.since[t];
    const rows = t === "leads" || !st.since[t] ? await allPages(t, params) : await rest("GET", t, { params: { ...params, limit: 1000 } });
    let changed = 0;
    const dirty = new Set(LS.get("lf_outbox", []).filter((o) => o.table === t).map((o) => String(o.id)));
    for (const R of rows) {
      if (!st.since[t] || R.updated_at > st.since[t]) st.since[t] = R.updated_at;
      const row = TABLES[t](R), k = keyOf(t, row);
      if (dirty.has(String(R.id))) continue;                      // our own queued change wins until it is uploaded
      st[t].set(k, row); changed++;
    }
    return changed;
  }
  async function pullAll() {
    let c = 0;
    for (const t of ["leads", "deals", "events", "notes"]) {
      if (t === "events" && st.caps.done === false) { /* fine: select * has no done columns */ }
      c += await pullTable(t);
    }
    if (c) saveCache();
    return c;
  }
  async function reconcile() {
    let c = 0;
    for (const t of ["leads", "deals", "events", "notes"]) {
      const ids = new Set((await allPages(t, { select: "id", order: "id.asc" })).map((r) => r.id));
      const dirty = new Set(LS.get("lf_outbox", []).filter((o) => o.table === t && o.kind === "insert").map((o) => String(o.id)));
      for (const k of [...st[t].keys()]) { const id = t === "leads" ? k : st[t].get(k).uuid; if (!ids.has(id) && !dirty.has(String(id))) { st[t].delete(k); c++; } }
    }
    if (c) saveCache();
    return c;
  }
  async function peopleRefresh() {
    st.people = await rest("GET", "profiles", { params: { select: pcols("id,username,display_name,role,active"), order: "display_name.asc" } });
    LS.set("lf_people", st.people);
  }
  async function pushProfileBits() {
    if (LS.get("lf_avatar_pending", false) && st.caps.avatar) { await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body: { avatar: LS.get("lf_avatar", "") || null }, prefer: "return=minimal" }); LS.set("lf_avatar_pending", false); }
    if (LS.get("lf_ext_pending", false) && st.caps.pext) {
      const e = LS.get("lf_ext", {}), body = Object.fromEntries(PEXT.map((k) => [k, e[k] || null])); body.banner = LS.get("lf_banner", "") || null;
      await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body, prefer: "return=minimal" }); LS.set("lf_ext_pending", false);
    }
  }
  async function cycleOnce(first) {
    if (st.busy || !uid()) return;
    st.busy = true;
    try {
      if (first) setSync("syncing");
      if (!st.profile) await fetchProfile();
      if (!st.profile.active) return onAuthLost("deactivated");
      await probeAll();
      await flush();
      await pushProfileBits();
      const changed = await pullAll();
      let extra = 0;
      if (Date.now() - st.lastRecon > 90000) { extra += await reconcile(); st.lastRecon = Date.now(); }
      if (Date.now() - st.lastBeat > 60000) {
        try { await peopleRefresh(); } catch (e) { if (!(e instanceof Http)) throw e; }
        try { await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body: { last_seen: nowIso(), status_text: "Online" }, prefer: "return=minimal" }); } catch (e) { if (!(e instanceof Http)) throw e; }
        st.lastBeat = Date.now();
        for (const k of Object.keys(st.caps)) if (st.caps[k] === false) st.caps[k] = null;
        const prev = st.profile; await fetchProfile();
        if (!st.profile.active) return onAuthLost("deactivated");
        if (prev && prev.role !== st.profile.role) emit("auth_changed");
      }
      st.loaded = true;
      if (changed || extra || first) emit("refresh");
      setSync(LS.get("lf_outbox", []).some((x) => x.blocked) ? "attention" : "synced");
    } catch (e) {
      if (e instanceof Offline) setSync("offline", "No connection");
      else if (e instanceof AuthLost) onAuthLost();
      else if (e instanceof AuthFail) onAuthLost();
      else setSync("error", String(e.message || e).slice(0, 200));
    } finally { st.busy = false; }
  }
  let loopT = null, beatT = null;
  /* 'Online' heartbeat every 30 s, also while the tab is in the background, so teammates see you consistently */
  async function beat() {
    if (!uid() || !navigator.onLine) return;
    try { await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body: { last_seen: nowIso(), status_text: "Online" }, prefer: "return=minimal" }); } catch (e) { }
  }
  function startLoop(first) {
    clearInterval(loopT); clearInterval(beatT);
    cycleOnce(first);
    loopT = setInterval(() => { if (!document.hidden) cycleOnce(false); }, 5000);
    beat(); beatT = setInterval(beat, 30000);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && uid()) { beat(); cycleOnce(false); checkVersion(false); } });
  window.addEventListener("online", () => { if (uid()) cycleOnce(false); });
  window.addEventListener("offline", () => { if (uid()) setSync("offline", "No connection"); });

  // ------------------------------------------------------------------ cosmetic profile (stays on this device)
  const PROFILE_DEFAULT = { name: "", email: "", phone: "", company: "Leafline Web Services", role: "", color: COLORS[0], goal: 25, country: "Canada", max_results: 120 };
  function cleanProfile(d, cur) {
    const out = { ...cur };
    if (!d || typeof d !== "object") return out;
    for (const k of ["name", "email", "phone", "company", "role", "country"]) if (k in d) out[k] = String(d[k] == null ? "" : d[k]).trim().slice(0, 80);
    if (COLORS.includes(d.color)) out.color = d.color;
    for (const [k, lo, hi] of [["goal", 1, 500], ["max_results", 10, 120]]) if (k in d) { const n = parseInt(d[k], 10); if (!isNaN(n)) out[k] = Math.max(lo, Math.min(hi, n)); }
    return out;
  }
  if (!st.cosmetic) st.cosmetic = { ...PROFILE_DEFAULT };

  // ------------------------------------------------------------------ deals / calendar maths
  function* dealPayments(d) {
    const closed = parseDay(d.closed_at), first = parseDay(d.first_bill) || closed;
    const up = closed && d.upfront > 0 ? [[closed, d.upfront, "upfront"]] : [];
    const monthly = function* () { let k = 0; while (first && d.monthly > 0 && (d.months === 0 || k < d.months)) { yield [addMonths(first, k, first.getUTCDate()), d.monthly, "monthly"]; k++; } };
    const A = up[Symbol.iterator](), B = monthly();
    let a = A.next(), b = B.next();
    while (!a.done || !b.done) {
      if (b.done || (!a.done && a.value[0] <= b.value[0])) { yield a.value; a = A.next(); } else { yield b.value; b = B.next(); }
    }
  }
  function paymentsBetween(d, lo, hi) { const out = []; for (const p of dealPayments(d)) { if (p[0] > hi) break; if (p[0] >= lo) out.push(p); } return out; }
  /* a payment counts as received only once someone confirmed it; keys look like "2026-11-03:upfront" */
  const confSet = (d) => new Set(String(d.confirmed || "").split(",").filter((k) => /^\d{4}-\d{2}-\d{2}:(upfront|monthly)$/.test(k)));
  const isConf = (set, dt, kind) => set.has(dayStr(dt) + ":" + kind);
  function dealSummary(d, today) {
    let got = 0, left = 0, waiting = 0, nWait = 0, nxt = null; const ongoing = d.monthly > 0 && d.months === 0, cs = confSet(d);
    for (const [dt, amt, kind] of dealPayments(d)) {
      if (dt <= today) { if (isConf(cs, dt, kind)) got += amt; else { waiting += amt; nWait++; } continue; }
      if (!nxt) nxt = [dt, amt];
      if (ongoing) break;
      left += amt;
    }
    return { collected: money(got), unconfirmed: money(waiting), unconfirmed_count: nWait, remaining: ongoing ? null : money(left), ongoing, next_date: nxt ? dayStr(nxt[0]) : "", next_amount: nxt ? money(nxt[1]) : 0 };
  }
  function* eventDates(e, lo, hi) {
    const start = parseDay(e.date); if (!start) return;
    const until = e.until ? parseDay(e.until) : null, end = until && until < hi ? until : hi, rep = e.repeat;
    if (rep === "none") { if (lo <= start && start <= end) yield start; return; }
    if (rep === "daily" || rep === "weekly") {
      const step = rep === "daily" ? 1 : 7; let d = addDays(start, Math.max(0, Math.floor(Math.round((lo - start) / 86400000) / step)) * step);
      while (d <= end) { if (d >= lo) yield d; d = addDays(d, step); }
      return;
    }
    const per = rep === "monthly" ? 1 : 12;
    let k = Math.max(0, Math.floor(((lo.getUTCFullYear() - start.getUTCFullYear()) * 12 + lo.getUTCMonth() - start.getUTCMonth()) / per) - 1);
    for (;;) { const d = addMonths(start, k * per, start.getUTCDate()); if (d > end) return; if (d >= lo) yield d; k++; }
  }
  const dealsList = () => [...st.deals.values()].sort((a, b) => (b.closed_at || "").localeCompare(a.closed_at || "") || b.id - a.id);
  function cleanDeal(d) {
    if (!d || typeof d !== "object") return [null, "Nothing to save."];
    const client = String(d.client || "").trim().slice(0, 80);
    if (!client) return [null, "Type the client's name."];
    const amt = {};
    for (const [k, label] of [["upfront", "Upfront amount"], ["monthly", "Monthly amount"]]) {
      const raw = String(d[k] == null ? "" : d[k]).replace(/\$/g, "").replace(/,/g, "").trim();
      const v = raw ? Number(raw) : 0;
      if (isNaN(v)) return [null, `${label} must be a number.`];
      if (!(v >= 0 && v <= 10000000)) return [null, `${label} must be between 0 and 10,000,000.`];
      amt[k] = money(v);
    }
    if (amt.upfront <= 0 && amt.monthly <= 0) return [null, "Enter an upfront amount, a monthly amount, or both."];
    const raw = String(d.months == null ? "" : d.months).trim(), months = raw ? Number(raw) : 0;
    if (isNaN(months) || months !== Math.floor(months) || months < 0 || months > 600) return [null, "Number of months must be a whole number from 1 to 600 (leave it empty if there is no end date)."];
    const closed = parseDay(d.closed_at); if (!closed) return [null, "Pick the date the deal was closed."];
    const first = parseDay(d.first_bill) || closed;
    return [{ client, upfront: amt.upfront, monthly: amt.monthly, months: amt.monthly > 0 ? months : 0, closed_at: dayStr(closed), first_bill: dayStr(first), notes: String(d.notes || "").trim().slice(0, 500) }, ""];
  }
  function cleanEvent(d) {
    if (!d || typeof d !== "object") return [null, "Nothing to save."];
    const title = String(d.title || "").trim().slice(0, 80); if (!title) return [null, "Type a title for the event."];
    const day = parseDay(d.date); if (!day) return [null, "Pick a date for the event."];
    let t = String(d.time || "").trim();
    if (t) { const m = /^(\d{1,2}):(\d{2})/.exec(t); if (!m || +m[1] > 23 || +m[2] > 59) return [null, "The time must look like 14:30 (leave it empty for an all-day event)."]; t = `${pad(+m[1])}:${m[2]}`; }
    const rep = String(d.repeat || "none"); if (!REPEATS.includes(rep)) return [null, "Pick how often the event repeats."];
    const rawUntil = String(d.until || "").trim(), until = rawUntil ? parseDay(rawUntil) : null;
    if (rawUntil && !until) return [null, "The repeat-until date is not valid."];
    if (until && until < day) return [null, "The repeat-until date can't be before the event date."];
    return [{ title, day: dayStr(day), start_time: t, color: EVENT_COLORS.includes(d.color) ? d.color : EVENT_COLORS[0], icon: EVENT_ICONS.includes(d.icon) ? d.icon : EVENT_ICONS[0], repeat_kind: rep, until: until && rep !== "none" ? dayStr(until) : null, notes: String(d.notes || "").trim().slice(0, 500), lead_id: String(d.lead_id || "").trim().slice(0, 200) || null }, ""];
  }
  function sanitizeBody(h) {
    if (typeof window.sanHTML === "function") { try { return window.sanHTML(h); } catch (e) { } }
    const d = document.createElement("div"); d.textContent = String(h || "").replace(/<[^>]*>/g, ""); return d.innerHTML;
  }

  // ------------------------------------------------------------------ the API the page calls
  const fail = (error) => ({ ok: false, error });
  const netErr = (e) => e instanceof Offline ? "You're offline." : e instanceof AuthLost ? "Signed out." : String(e.message || e).slice(0, 160);
  const isAdmin = () => ((meOf() || {}).role === "admin");
  const names = () => Object.fromEntries((st.people || []).map((p) => [p.id, p.display_name]));
  const leadDict = (l) => { const [o, h, n] = openStatus(l.hours); return { id: l.id, name: l.name, btype: l.btype || "Other", phone: l.phone, owner: l.owner || NA, rating: l.rating || NA, reviews: l.reviews || NA, address: l.address || NA, website: l.website || NA, notes: l.notes, status: l.status || "none", called_at: l.called_at || "", open: o, hours: h, open_note: n, search: l.search || "", meeting_at: l.meeting_at || "", called_by: l.called_by || "", called_by_name: (l.called_by && names()[l.called_by]) || "" }; };
  const revNum = (l) => { const n = parseInt(String(l.reviews).replace(/\D/g, ""), 10); return isNaN(n) ? 0 : n; };
  const cmpName = (a, b) => String(a).toLowerCase() < String(b).toLowerCase() ? -1 : String(a).toLowerCase() > String(b).toLowerCase() ? 1 : 0;

  function statsNow() {
    const leads = [...st.leads.values()], today = parseDay(todayStr());
    const keys = [], labels = [];
    for (let i = 6; i >= 0; i--) { const d = addDays(today, -i); keys.push(dayStr(d)); labels.push(SHORT[wd(d)]); }
    const total = leads.length, uncalled = leads.filter((l) => l.status === "none").length, counts = {};
    leads.forEach((l) => (counts[l.status] = (counts[l.status] || 0) + 1));
    const cnt = (f) => { const o = {}; leads.forEach((l) => { if (f(l)) { const k = (f.k(l) || "").slice(0, 10); o[k] = (o[k] || 0) + 1; } }); return o; };
    const addedF = Object.assign((l) => (l.added_at || "").slice(0, 10) >= keys[0], { k: (l) => l.added_at });
    const callsF = Object.assign((l) => l.status !== "none" && (l.called_at || "").slice(0, 10) >= keys[0], { k: (l) => l.called_at });
    const meetsF = Object.assign((l) => l.status === "green" && (l.called_at || "").slice(0, 10) >= keys[0], { k: (l) => l.called_at });
    const added = cnt(addedF), calls = cnt(callsF), meets = cnt(meetsF);
    const conv = keys.map((k) => { let n = 0, g = 0; leads.forEach((l) => { if (l.status !== "none" && (l.called_at || "").slice(0, 10) <= k) { n++; if (l.status === "green") g++; } }); return n ? Math.round(1000 * g / n) / 10 : 0; });
    const tmap = new Map(); leads.forEach((l) => { const kk = (l.btype || "").toLowerCase(); const cur = tmap.get(kk); if (!cur) tmap.set(kk, { name: l.btype || "", count: 1 }); else { cur.count++; if ((l.btype || "") < cur.name) cur.name = l.btype || ""; } });
    const types = [...tmap.values()].sort((a, b) => b.count - a.count || (a.name < b.name ? -1 : 1)).slice(0, 5).map((t) => ({ name: t.name || "Other", count: t.count }));
    const sA = keys.map((k) => added[k] || 0), sC = keys.map((k) => calls[k] || 0), sM = keys.map((k) => meets[k] || 0), called = total - uncalled, green = counts.green || 0, sum = (a) => a.reduce((x, y) => x + y, 0);
    return { total, uncalled, called, meetings: green, interested: counts.yellow || 0, noanswer: counts.orange || 0, rejected: counts.red || 0, conversion: called ? Math.round(1000 * green / called) / 10 : 0,
      series: { added: sA, calls: sC, meets: sM, conv }, labels, week: { added: sum(sA), calls: sum(sC), meets: sum(sM), conv: Math.round((conv[6] - conv[0]) * 10) / 10 }, types, today_calls: sC[6],
      goal: st.cosmetic.goal, money: moneyNow() };
  }
  function moneyNow() {
    const today = parseDay(todayStr()), w0 = addDays(today, -wd(today)), w1 = addDays(w0, 6), nd = dim(today.getUTCFullYear(), today.getUTCMonth());
    const m0 = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 1)), m1 = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), nd));
    const lo = w0 < m0 ? w0 : m0, hi = w1 > m1 ? w1 : m1;
    const daily = Array(nd).fill(0), dmade = Array(nd).fill(0), wdays = Array(7).fill(0), wpay = [], todo = []; let collected = 0, onWay = 0, mrr = 0, closedWeek = 0, waiting = 0, made = 0;
    const deals = dealsList();
    for (const d of deals) {
      const sm = dealSummary(d, today), cs = confSet(d); collected += sm.collected; waiting += sm.unconfirmed; onWay += sm.remaining || 0;
      if (sm.unconfirmed_count) for (const [dt, amt, kind] of dealPayments(d)) { if (dt > today) break; if (!isConf(cs, dt, kind)) todo.push({ deal_id: d.id, client: d.client, date: dayStr(dt), amount: money(amt), kind }); }
      if (d.monthly > 0 && sm.next_date) mrr += d.monthly;
      const c = parseDay(d.closed_at); if (c && w0 <= c && c <= w1) closedWeek++;
      for (const [dt, amt, kind] of paymentsBetween(d, lo, hi)) {
        const ok = isConf(cs, dt, kind);
        if (m0 <= dt && dt <= m1) { daily[dt.getUTCDate() - 1] += amt; if (ok) { made += amt; dmade[dt.getUTCDate() - 1] += amt; } }
        if (w0 <= dt && dt <= w1) { wdays[Math.round((dt - w0) / 86400000)] += amt; wpay.push({ deal_id: d.id, client: d.client, date: dayStr(dt), amount: money(amt), kind, paid: ok, due: dt <= today }); }
      }
    }
    wpay.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : cmpName(a.client, b.client)));
    todo.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : cmpName(a.client, b.client)));
    const sum = (a) => a.reduce((x, y) => x + y, 0), rest_ = sum(daily) - made, got = sum(wpay.filter((p) => p.paid).map((p) => p.amount));
    const label = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" }).format(today);
    return { today: dayStr(today), month: { label, made: money(made), rest: money(rest_), total: money(made + rest_), daily: daily.map(money), daily_made: dmade.map(money), today: today.getUTCDate(), days: nd },
      week: { start: dayStr(w0), end: dayStr(w1), projected: money(sum(wdays)), received: money(got), upcoming: money(sum(wdays) - got), closed: closedWeek, payments: wpay,
        days: wdays.map((a, i) => ({ label: SHORT[i], date: dayStr(addDays(w0, i)), amount: money(a), future: addDays(w0, i) > today })) },
      all: { collected: money(collected), on_the_way: money(onWay), mrr: money(mrr), deals: deals.length, unconfirmed: money(waiting), to_confirm: todo.slice(-200) } };
  }
  function msgErr(e) {
    if (e instanceof Offline) return { ok: false, offline: true, error: "You're offline." };
    if (e instanceof AuthLost) return fail("Signed out.");
    if (e instanceof Http) {
      const b = e.body && typeof e.body === "object" ? e.body : {};
      if (e.status === 404 && (["PGRST202", "42883"].includes(b.code) || /Could not find/.test(JSON.stringify(b)))) return { ok: false, missing: true, error: "Messages need the 8th database update. Ask an admin to run it (see SETUP_SUPABASE.md)." };
      return { ok: false, status: e.status, error: String(b.message || b.error || e.message).slice(0, 300) };
    }
    return fail(String(e.message || e).slice(0, 300));
  }
  const guardNet = async (f) => { try { return await f(); } catch (e) { return fail(netErr(e)); } };

  const API = {
    async boot() {
      if (!st.boot) {
        st.boot = true;
        if (st.session) {
          await loadCache();
          try { await fetchProfile(); if (!st.profile.active) onAuthLost("deactivated"); else startLoop(true); }
          catch (e) {
            if (e instanceof AuthLost || e instanceof AuthFail) onAuthLost();
            else { if (!st.me) onAuthLost(); else { setSync("offline", "No connection"); startLoop(true); } }
          }
        }
      }
      const me = st.session ? meOf() || (st.me ? { ...st.me, avatar: LS.get("lf_avatar", ""), ext: { ...Object.fromEntries(PEXT.map((k) => [k, ""])), ...LS.get("lf_ext", {}), banner: LS.get("lf_banner", "") } } : null) : null;
      return { profile: st.cosmetic, stats: statsNow(), find: API.get_find(), called: API.get_called(), current: null, running: false, db_path: "Shared database (website)", deals: API.get_deals(), auth: { me, sync: st.sync, people: st.people } };
    },
    get_profile() { return st.cosmetic; },
    save_profile(d) { st.cosmetic = cleanProfile(d, st.cosmetic); LS.set("lf_profile", st.cosmetic); return st.cosmetic; },
    async sign_in(username, password) {
      try { const me = await signIn(String(username || ""), String(password || "")); return { ok: true, me }; }
      catch (e) { return fail(e instanceof AuthFail ? e.message : e instanceof Offline ? "Can't reach the Leafline server. Check your internet connection and try again." : "Sign-in failed: " + String(e.message || e).slice(0, 120)); }
    },
    async sign_out() {
      try { await flush(); } catch (e) { }
      const p = pendingCount() + LS.get("lf_outbox", []).filter((o) => o.blocked).length + (LS.get("lf_avatar_pending", false) && st.caps.avatar ? 1 : 0) + (LS.get("lf_ext_pending", false) && st.caps.pext ? 1 : 0);
      if (p) return { ok: false, pending: p };
      try { fetch(SB + "/auth/v1/logout?scope=local", { method: "POST", headers: { apikey: KEY, Authorization: "Bearer " + st.session.access_token } }).catch(() => { }); } catch (e) { }
      clearInterval(loopT);
      LS.del("lf_session"); LS.del("lf_me"); ["lf_avatar", "lf_avatar_pending", "lf_ext", "lf_banner", "lf_ext_pending", "lf_media", "lf_board"].forEach(LS.del);
      st.session = null; st.profile = null; st.me = null; clearData(); setSync("signed_out");
      return { ok: true };
    },
    async set_avatar(d) {
      d = String(d || "");
      if (d && !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(d)) return fail("That doesn't look like a picture.");
      if (d.length > 60000) return fail("That picture is too large.");
      if (!uid()) return fail("Sign in first.");
      LS.set("lf_avatar", d); LS.set("lf_avatar_pending", true); cycleOnce(false);
      return { ok: true, shared: !!st.caps.avatar };
    },
    async set_profile_ext(d) {
      d = d && typeof d === "object" ? d : {};
      if (!uid()) return fail("Sign in first.");
      const out = {}, lim = { title: 40, bio: 280, thought: 140, mood: 8 };
      for (const [k, n] of Object.entries(lim)) if (k in d) out[k] = k === "bio" ? String(d[k] || "").trim().split(/\r?\n/).map((l) => l.trim()).join("\n").slice(0, n) : String(d[k] || "").split(/\s+/).filter(Boolean).join(" ").slice(0, n);
      if ("accent" in d) { const a = String(d.accent || ""); if (a && !/^#[0-9A-Fa-f]{6}$/.test(a)) return fail("Pick a colour from the list."); out.accent = a; }
      if ("banner" in d) { const b = String(d.banner || ""); if (b && !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(b)) return fail("That doesn't look like a picture."); if (b.length > 150000) return fail("That banner is too large."); LS.set("lf_banner", b); }
      const cur = { ...Object.fromEntries(PEXT.map((k) => [k, ""])), ...LS.get("lf_ext", {}) };
      if ("thought" in out && out.thought !== cur.thought) cur.thought_at = out.thought ? nowIso() : "";
      for (const k of PEXT) if (k in out) cur[k] = out[k];
      LS.set("lf_ext", cur); LS.set("lf_ext_pending", true); cycleOnce(false);
      const me = meOf();
      return { ok: true, shared: !!st.caps.pext, ext: me ? me.ext : cur };
    },
    async get_person(pid) {
      return guardNet(async () => {
        const rows = await rest("GET", "profiles", { params: { id: "eq." + String(pid), select: pcols("id,username,display_name,role,active,last_seen") + (st.caps.pext ? ",banner" : "") } });
        return { ok: !!rows.length, person: rows[0] || null };
      });
    },
    async change_password(nw) {
      nw = String(nw || ""); const me = meOf() || {};
      if (nw.length < 8 || !/[A-Za-z]/.test(nw) || !/\d/.test(nw)) return fail("Use at least 8 characters with a letter and a number.");
      if (nw.toLowerCase() === (me.username || "") + "123") return fail("Pick something different from the starter password.");
      try {
        await call("PUT", "/auth/v1/user", { body: { password: nw } });
        await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body: { must_change_password: false }, prefer: "return=minimal" });
        if (st.profile) st.profile.must_change_password = false; cacheMe();
      } catch (e) { return fail(e instanceof Offline ? "No connection. Try again when you are online." : "Could not change the password: " + String(e.message).slice(0, 120)); }
      return { ok: true, me: meOf() };
    },
    sync_status() { return st.sync; },
    sync_retry() { LS.set("lf_outbox", LS.get("lf_outbox", []).map((o) => ({ ...o, blocked: false }))); flush(); return { ok: true }; },
    sync_details() { const q = LS.get("lf_outbox", []); return { pending: q.filter((o) => !o.blocked), blocked: q.filter((o) => o.blocked), conflicts: [] }; },
    get_people() { return st.people; },
    // ----- Messages (11.4): only the msg_* database functions and the private file bucket; the database enforces every rule
    async sb_rpc(fn, args) {
      if (!/^(msg|me|note)_[a-z_]{2,40}$/.test(String(fn)) || !args || typeof args !== "object" || Array.isArray(args)) return fail("Not allowed.");
      try { return { ok: true, data: await call("POST", "/rest/v1/rpc/" + fn, { body: args }) }; } catch (e) { return msgErr(e); }
    },
    async sb_storage(op, paths, opts) {
      paths = Array.isArray(paths) ? paths : [paths];
      if (!paths.length || paths.length > 100 || !paths.every((x) => /^[0-9a-f-]{36}\/[0-9a-f-]{36}\/[A-Za-z0-9._-]{1,180}$/.test(String(x)))) return fail("Not allowed.");
      try {
        if (op === "sign_upload") { const r = await call("POST", "/storage/v1/object/upload/sign/message-files/" + paths[0], { body: {} }); return { ok: true, url: SB + "/storage/v1" + r.url }; }
        if (op === "sign") {
          const exp = Math.max(60, Math.min(parseInt((opts || {}).expires || 3600, 10) || 3600, 86400));
          const r = await call("POST", "/storage/v1/object/sign/message-files", { body: { expiresIn: exp, paths } });
          return { ok: true, urls: Object.fromEntries((r || []).map((x) => [x.path, x.signedURL ? SB + "/storage/v1" + x.signedURL : null])) };
        }
        if (op === "remove") { await call("DELETE", "/storage/v1/object/message-files", { body: { prefixes: paths } }); return { ok: true }; }
      } catch (e) { return msgErr(e); }
      return fail("Not allowed.");
    },
    async sb_group_picture(dataUrl) {
      const m = /^data:image\/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$/.exec(String(dataUrl || "")); if (!m) return fail("Pick a JPG, PNG or WebP picture.");
      let raw; try { raw = Uint8Array.from(atob(m[2]), (c) => c.charCodeAt(0)); } catch (e) { return fail("That picture is damaged."); }
      if (raw.length > 400000) return fail("That picture is too big.");
      const name = `${uid()}/group-${uuid4().replace(/-/g, "").slice(0, 12)}.${m[1] === "jpeg" ? "jpg" : m[1]}`;
      try {
        const r = await fetch(SB + "/storage/v1/object/media/" + name, { method: "POST", headers: { apikey: KEY, Authorization: "Bearer " + (await token()), "Content-Type": "image/" + m[1], "x-upsert": "false" }, body: raw });
        if (!r.ok) return fail("Couldn't upload the picture (" + r.status + ").");
        return { ok: true, url: SB + "/storage/v1/object/public/media/" + name };
      } catch (e) { return msgErr(e); }
    },
    async sb_session() {
      try { const t = await token(); return { ok: true, url: SB, key: KEY, token: t, uid: uid(), realtime: (C.realtime || SB.replace(/^http/, "ws") + "/realtime/v1/websocket") }; }
      catch (e) { return msgErr(e); }
    },
    get_prefs() { return st.prefs; },
    set_pref(k, v) { k = String(k).replace(/[^A-Za-z0-9_]/g, "").slice(0, 30); const val = JSON.stringify(v); if (!k || val.length > 2000) return { ok: false }; st.prefs[k] = v; LS.set("lf_prefs", st.prefs); return { ok: true }; },

    // ----- leads
    get_find() { return [...st.leads.values()].filter((l) => l.status === "none").sort((a, b) => revNum(b) - revNum(a) || cmpName(a.name, b.name)).map(leadDict); },
    get_called() {
      return [...st.leads.values()].filter((l) => l.status !== "none").sort((a, b) => cmpName(a.btype, b.btype) || (b.called_at || "").localeCompare(a.called_at || "") || cmpName(a.name, b.name)).map(leadDict);
    },
    stats() { return statsNow(); },
    async mark(ids, status) {
      if (!STATUS.includes(status) || !Array.isArray(ids)) return { ok: false };
      const when = status === "none" ? "" : nowLocal(), me = uid();
      for (const i of ids) {
        const l = st.leads.get(String(i)); if (!l) continue;
        const was = l.status;
        l.status = status; l.called_at = when;
        if (status === "none") l.called_by = ""; else if (was !== status) l.called_by = me;
        const body = { status, called_at: when ? localToISO(when) : null };
        if (status !== "none" && was !== status) body.called_by = me;
        enqueue({ kind: "patch", table: "leads", id: l.id, body });
        if (OUTCOME[status] && was !== status) {
          const opid = await uuid5(`${l.id}|${body.called_at}|${status}|${me}`);
          enqueue({ kind: "insert", table: "call_log", id: opid, conflict: "client_op_id", body: { client_op_id: opid, lead_id: l.id, employee_id: me, phone: l.phone, started_at: body.called_at, outcome: OUTCOME[status], notes: l.notes, source: "app" } });
        }
      }
      saveCache();
      return { ok: true, n: ids.length };
    },
    save_lead(id, owner, notes) {
      const l = st.leads.get(String(id)); const ow = (owner || "").trim().slice(0, 80) || NA;
      if (l) { l.owner = ow; l.notes = (notes || "").trim().slice(0, 2000); enqueue({ kind: "patch", table: "leads", id: l.id, body: { owner_name: l.owner, notes: l.notes } }); saveCache(); }
      return { ok: true, owner: ow };
    },
    set_meeting(id, when) {
      let w = String(when || "").trim().replace("T", " ");
      if (w) { if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(w) || !localToISO(w)) return fail("Pick a valid date and time."); w = w.slice(0, 16); }
      const l = st.leads.get(String(id)); if (!l) return { ok: false };
      l.meeting_at = w; enqueue({ kind: "patch", table: "leads", id: l.id, body: { meeting_at: w ? localToISO(w) : null } }); saveCache();
      return { ok: true };
    },
    open_site(id) {
      const l = st.leads.get(String(id)), w = l && l.website;
      if (!w || w === NA) return { ok: false };
      window.open(/^http/i.test(w) ? w : "http://" + w, "_blank", "noopener"); return { ok: true };
    },
    search() { return fail("Finding new businesses runs in the Leafline desktop app. Everything it finds shows up here automatically."); },
    stop() { return { ok: true }; },
    export_csv(called, scope) {
      const rows = called ? API.get_called() : API.get_find(), extra = (id) => (st.leads.get(id) || {}).website || NA;
      const lab = { none: "Not called yet", green: "Called - Meeting set up", yellow: "Called - Interested", orange: "Called - No answer", red: "Called - Not interested" };
      const head = ["Business type", "Company", "Phone", "Owner", "Open now", "Hours today", "Rating", "Reviews", "Website", "Address", "Notes"];
      const table = [(called ? ["Result"] : []).concat(called ? head.slice(0, 4).concat(["Last called"], head.slice(4)) : head)];
      for (const l of rows) {
        const r = [l.btype, l.name, l.phone, l.owner]; if (called) r.push(l.called_at);
        r.push({ open: "Open", closed: "Closed" }[l.open] || NA, l.hours, l.rating, l.reviews, extra(l.id), l.address, l.notes);
        table.push((called ? [lab[l.status]] : []).concat(r));
      }
      download(called ? "leafline_called_leads.csv" : "leafline_leads.csv", toCsv(table));
      return { ok: true, path: "", n: rows.length };
    },

    // ----- deals
    get_deals() { const today = parseDay(todayStr()); return dealsList().map((d) => ({ id: d.id, client: d.client, upfront: d.upfront, monthly: d.monthly, months: d.months, closed_at: d.closed_at, first_bill: d.first_bill, notes: d.notes, ...dealSummary(d, today) })); },
    save_deal(d) {
      const [c, err] = cleanDeal(d); if (err) return fail(err);
      const lid = parseInt(d.id || 0, 10), uu = lid && byLid.deals.get(lid), cur = uu && st.deals.get(uu);
      if (cur) { Object.assign(cur, c); enqueue({ kind: "patch", table: "deals", id: cur.uuid, body: c }); }
      else {
        const id = uuid4(), row = dealIn({ id, ...c, created_at: nowIso() }); st.deals.set(id, row);
        enqueue({ kind: "insert", table: "deals", id, body: { id, client_op_id: id, ...c, owner_id: uid(), created_by: uid(), source: "app" } });
      }
      saveCache(); return { ok: true };
    },
    confirm_payment(id, day, kind, on = true) {
      const uu = byLid.deals.get(parseInt(id, 10)), d = uu && st.deals.get(uu); if (!d) return fail("Deal not found.");
      const dt = parseDay(day); if (!dt || !["upfront", "monthly"].includes(kind)) return fail("That payment doesn't exist.");
      if (on && dt > parseDay(todayStr())) return fail("This payment isn't due yet. You can confirm it on or after its date.");
      if (!paymentsBetween(d, dt, dt).some((p) => p[2] === kind)) return fail("That payment doesn't exist.");
      if (st.caps.paid === false) return fail("Confirming payments needs the 7th database update. Ask an admin to run it (see SETUP_SUPABASE.md).");
      const cs = confSet(d), k = dayStr(dt) + ":" + kind; if (on) cs.add(k); else cs.delete(k);
      d.confirmed = [...cs].sort().join(","); enqueue({ kind: "patch", table: "deals", id: d.uuid, body: { confirmed: d.confirmed } }); saveCache();
      return { ok: true, confirmed: !!on };
    },
    delete_deal(id) {
      const uu = byLid.deals.get(parseInt(id, 10)); if (!uu) return { ok: false };
      st.deals.delete(uu); enqueue({ kind: "delete", table: "deals", id: uu }); saveCache(); return { ok: true };
    },

    // ----- calendar
    get_calendar(lo, hi) {
      lo = parseDay(lo); hi = parseDay(hi);
      if (!lo || !hi || hi < lo || (hi - lo) / 86400000 > 400) return [];
      const today = parseDay(todayStr()), items = [], nm = names();
      for (const l of st.leads.values()) if (l.status === "green" && l.meeting_at) { const d = l.meeting_at.slice(0, 10); if (d >= dayStr(lo) && d <= dayStr(hi)) items.push({ src: "meeting", key: `m:${l.id}`, title: l.name || "", date: d, time: l.meeting_at.slice(11, 16), lead_id: l.id, phone: l.phone || "", owner: l.owner && l.owner !== NA ? l.owner : "" }); }
      for (const d of dealsList()) {
        const c = parseDay(d.closed_at); if (c && lo <= c && c <= hi) items.push({ src: "closed", key: `c:${d.id}`, title: d.client, date: dayStr(c), time: "", deal_id: d.id });
        for (const [dt, amt, kind] of paymentsBetween(d, lo, hi)) items.push({ src: "payment", key: `p:${d.id}:${dayStr(dt)}:${kind}`, title: d.client, date: dayStr(dt), time: "", amount: money(amt), kind, paid: confSet(d).has(dayStr(dt) + ":" + kind), due: dt <= today, deal_id: d.id });
      }
      for (const e of st.events.values()) {
        const ld = e.lead_id && st.leads.get(e.lead_id);
        for (const dt of eventDates(e, lo, hi)) items.push({ src: "event", key: `e:${e.id}:${dayStr(dt)}`, id: e.id, title: e.title, date: dayStr(dt), start: e.date, time: e.time, color: e.color, icon: e.icon, repeat: e.repeat, until: e.until, notes: e.notes, lead_id: e.lead_id, lead_name: ld ? ld.name : "", phone: ld ? ld.phone : "", assigned_to: e.assigned_to, assigned_name: nm[e.assigned_to] || "", created_name: nm[e.created_by] || "", done: e.done });
      }
      const order = { meeting: 0, event: 1, payment: 2, closed: 3 };
      items.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0) || String(a.time || "").localeCompare(String(b.time || "")) || order[a.src] - order[b.src] || cmpName(a.title, b.title));
      return items;
    },
    save_event(d) {
      const [c, err] = cleanEvent(d); if (err) return fail(err);
      let who = String(d.assigned_to || ""); if (who && !(st.people || []).some((p) => p.id === who)) who = "";
      const body = { ...c, assigned_to: who || null };
      if (body.lead_id && !st.leads.has(body.lead_id)) body.lead_id = null;
      const lid = parseInt(d.id || 0, 10), uu = lid && byLid.events.get(lid), cur = uu && st.events.get(uu);
      if (cur) { Object.assign(cur, eventIn({ id: cur.uuid, ...body, created_by: cur.created_by, done: cur.done, done_at: cur.done_at })); enqueue({ kind: "patch", table: "events", id: cur.uuid, body }); }
      else { const id = uuid4(); st.events.set(id, eventIn({ id, ...body, created_by: uid() })); enqueue({ kind: "insert", table: "events", id, body: { id, client_op_id: id, ...body, created_by: uid(), source: "app" } }); }
      saveCache(); return { ok: true };
    },
    delete_event(id) { const uu = byLid.events.get(parseInt(id, 10)); if (!uu) return { ok: false }; st.events.delete(uu); enqueue({ kind: "delete", table: "events", id: uu }); saveCache(); return { ok: true }; },
    set_event_done(id, done) {
      const uu = byLid.events.get(parseInt(id, 10)), e = uu && st.events.get(uu); if (!e) return { ok: false };
      e.done = !!done; e.done_at = done ? nowIso() : "";
      if (st.caps.done) enqueue({ kind: "patch", table: "events", id: uu, body: { done: !!done, done_at: done ? nowIso() : null } });
      saveCache(); return { ok: true };
    },

    // ----- notes and scripts
    get_notes() {
      const me = uid(), nm = names();
      return [...st.notes.values()].filter((n) => n.scope === "shared" || n.owner_id === me || !n.owner_id).sort((a, b) => cmpName(a.title, b.title)).map((n) => ({
        id: n.id, kind: n.kind, scope: n.scope, title: n.title || "Untitled", folder: n.folder, body: n.body, owner_id: n.owner_id || me, owner: nm[n.owner_id || me] || "You", mine: (n.owner_id || me) === me,
        created: isoToLocal(n.created_at), rid: n.uuid || "", unsynced: LS.get("lf_outbox", []).some((o) => o.table === "notes" && String(o.id) === n.uuid) }));
    },
    save_note(d) {
      if (!d || typeof d !== "object") return fail("Nothing to save.");
      const kind = d.kind === "script" ? "script" : "note"; let scope = d.scope === "shared" ? "shared" : "personal";
      const title = String(d.title || "").trim().slice(0, 120) || "Untitled", folder = String(d.folder || "").trim().slice(0, 60);
      let body = String(d.body || ""); if (body.length > 600000) return fail("This is too long to save (limit about 600,000 characters).");
      if (kind === "script") body = sanitizeBody(body);
      const me = uid(), lid = parseInt(d.id || 0, 10), uu = lid && byLid.notes.get(lid), cur = uu && st.notes.get(uu);
      if (cur) {
        if (cur.scope === "personal" && cur.owner_id && cur.owner_id !== me) return fail("That note belongs to someone else.");
        if (cur.owner_id && cur.owner_id !== me) scope = cur.scope;
        if (cur.body !== body || cur.title !== title || cur.folder !== folder || cur.scope !== scope || cur.kind !== kind) {
          Object.assign(cur, { kind, scope, title, folder, body });
          const patch = { kind, title, folder, body }; if (!cur.owner_id || cur.owner_id === me) patch.scope = scope;
          enqueue({ kind: "patch", table: "notes", id: cur.uuid, body: patch });
        }
        saveCache(); return { ok: true, id: cur.id, body };
      }
      const id = uuid4(), row = noteIn({ id, kind, scope, title, folder, body, owner_id: me, created_at: nowIso() }); st.notes.set(id, row);
      enqueue({ kind: "insert", table: "notes", id, body: { id, client_op_id: id, kind, scope, title, folder, body, owner_id: me } });
      saveCache(); return { ok: true, id: row.id, body };
    },
    delete_note(id) {
      const uu = byLid.notes.get(parseInt(id, 10)), n = uu && st.notes.get(uu); if (!n) return { ok: true };
      if (n.owner_id && n.owner_id !== uid() && !(n.scope === "shared" && isAdmin())) return fail("Only the owner can delete this.");
      st.notes.delete(uu); enqueue({ kind: "delete", table: "notes", id: uu }); saveCache(); return { ok: true };
    },

    // ----- shared call log
    async get_calls(f) {
      f = f && typeof f === "object" ? f : {};
      const nm = names(), params = { select: "*", order: "started_at.desc" }, and = [];
      if (f.employee) params.employee_id = f.employee === "none" ? "is.null" : "eq." + f.employee;
      if (OUTCOMES.includes(f.outcome)) params.outcome = "eq." + f.outcome;
      if (/^\d{4}-\d{2}-\d{2}$/.test(f.from || "")) and.push("started_at.gte." + localToISO(f.from + " 00:00"));
      if (/^\d{4}-\d{2}-\d{2}$/.test(f.to || "")) and.push("started_at.lt." + localToISO(dayStr(addDays(parseDay(f.to), 1)) + " 00:00"));
      if (and.length) params.and = "(" + and.join(",") + ")";
      let rows, stale = false;
      try { rows = f.q ? await allPages("call_log", params) : await rest("GET", "call_log", { params: { ...params, limit: 400 } }); LS.set("lf_calls", rows.slice(0, 400)); }
      catch (e) { if (e instanceof Offline) { rows = LS.get("lf_calls", []); stale = true; } else if (e instanceof AuthLost) return fail("Signed out."); else return fail("Couldn't load the call log: " + String(e.message).slice(0, 140)); }
      let out = rows.map((r) => { const l = st.leads.get(r.lead_id) || {}; return { id: r.id, at: r.started_at, who_id: r.employee_id, who: nm[r.employee_id] || "Unassigned", business: l.name || "", phone: r.phone || l.phone || "", outcome: r.outcome, notes: r.notes || "", legacy: r.source === "legacy_status" || r.source === "backfill", pending: false }; });
      const have = new Set(out.map((o) => o.id));
      for (const q of LS.get("lf_outbox", []).filter((o) => o.table === "call_log")) {
        const b = q.body; if (have.has(b.client_op_id) || (f.employee && b.employee_id !== f.employee) || (f.outcome && b.outcome !== f.outcome)) continue;
        const l = st.leads.get(b.lead_id) || {};
        out.push({ id: "q" + b.client_op_id, at: b.started_at, who_id: b.employee_id, who: nm[b.employee_id] || "Me", business: l.name || "", phone: b.phone || l.phone || "", outcome: b.outcome, notes: b.notes || "", legacy: false, pending: true });
      }
      if (f.q) {
        const qq = f.q.trim().toLowerCase(), dq = /[a-z]/.test(qq) ? "" : qq.replace(/\D/g, "");
        out = out.filter((o) => o.business.toLowerCase().includes(qq) || (o.notes || "").toLowerCase().includes(qq) || (dq && String(o.phone || "").replace(/\D/g, "").includes(dq)));
      }
      out.sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));
      return { ok: true, rows: out.slice(0, 1000), stale, capped: out.length > 1000 };
    },
    async log_call(d) {
      d = d && typeof d === "object" ? d : {};
      const outcome = String(d.outcome || ""); if (!OUTCOMES.includes(outcome)) return fail("Pick what happened on the call.");
      const me = uid(); if (!me) return fail("Sign in first.");
      let lid = String(d.lead_id || ""), phone = String(d.phone || "").trim().slice(0, 40); const l = lid ? st.leads.get(lid) : null;
      if (lid && !l) lid = ""; if (l && !phone) phone = l.phone || "";
      if (!lid && !phone) return fail("Choose the business, or type the phone number.");
      const when = localToISO(String(d.when || "").replace("T", " ").slice(0, 16)) || nowIso(), opid = uuid4();
      enqueue({ kind: "insert", table: "call_log", id: opid, conflict: "client_op_id", body: { client_op_id: opid, lead_id: lid || null, employee_id: me, phone, started_at: when, outcome, notes: String(d.notes || "").slice(0, 1000), source: "app" } });
      return { ok: true };
    },

    // ----- team + administrators
    async get_team() {
      const days = 14;
      try {
        const today = parseDay(todayStr()), frm = addDays(today, -(days - 1));
        const prof = await rest("GET", "profiles", { params: { select: pcols("id,username,display_name,role,active,last_seen"), order: "display_name.asc" } });
        const stats = await call("POST", "/rest/v1/rpc/daily_stats", { body: { p_from: dayStr(frm), p_to: dayStr(today) } });
        const act = await rest("GET", "activity", { params: { select: "*", order: "created_at.desc", limit: 40 } });
        const sett = await rest("GET", "settings", { params: { key: "eq.daily_targets", select: "value" } });
        const deals = await rest("GET", "deals", { params: { select: "upfront,closed_at,owner_id", closed_at: "gte." + dayStr(frm) } });
        const tasks = {};
        if (st.caps.done) { try { const since = localToISO(todayStr() + " 00:00"); for (const r of await rest("GET", "events", { params: { select: "done_by", done: "eq.true", done_at: "gte." + since } })) tasks[r.done_by] = (tasks[r.done_by] || 0) + 1; } catch (e) { if (!(e instanceof Http)) throw e; } }
        st.people = prof.map((p) => Object.fromEntries(["id", "username", "display_name", "role", "active", "avatar", ...PEXT, ...MEDIA].map((k) => [k, p[k]]))); LS.set("lf_people", st.people);
        const targets = { calls: 100, connections: 20, meetings: 3, sales: 1, ...((sett[0] && sett[0].value) || {}) }, nm = names(), now = Date.now();
        const zero = () => ({ calls: 0, connections: 0, prospects: 0, meetings: 0, sales: 0 }), keys = Object.keys(zero());
        const by = {}; for (const r of stats) { (by[r.day] = by[r.day] || {})[r.employee_id] = Object.fromEntries(keys.map((k) => [k, Number(r[k] || 0)])); }
        const tdy = by[dayStr(today)] || {}, people = [];
        for (const p of prof) {
          if (!p.active) continue;
          const mine = { ...zero(), ...(tdy[p.id] || {}) }, last = act.find((a) => a.employee_id === p.id), per = zero();
          for (const dd of Object.values(by)) for (const k of keys) per[k] += (dd[p.id] || {})[k] || 0;
          const online = p.last_seen ? (now - new Date(p.last_seen).getTime()) / 1000 < 120 : false;
          people.push({ ...pub(p), name: p.display_name, online, today: { ...mine, tasks: tasks[p.id] || 0 }, period: per,
            progress: Math.round(100 * mine.calls / Math.max(1, targets.calls)), last: last ? { text: last.summary, at: last.created_at } : null });
        }
        const tot = zero(); for (const e of Object.values(tdy)) if (e) for (const k of keys) tot[k] += e[k] || 0;
        const series = []; for (let i = 0; i < days; i++) { const d = dayStr(addDays(frm, i)), row = zero(); for (const e of Object.values(by[d] || {})) for (const k of keys) row[k] += e[k]; series.push({ day: d, ...row }); }
        const mon = addDays(today, -wd(today));
        const wk = (a, b) => { const r = zero(); for (const x of series) if (dayStr(a) <= x.day && x.day <= dayStr(b)) for (const k of keys) r[k] += x[k]; return r; };
        const closedToday = deals.filter((d) => d.closed_at === dayStr(today));
        const out = { ok: true, stale: false, tasks_enabled: !!st.caps.done, today: dayStr(today), targets, totals: tot, people, series, week: wk(mon, today), last_week: wk(addDays(mon, -7), addDays(mon, -1)),
          deals_today: closedToday.length, revenue_today: money(closedToday.reduce((s, d) => s + num(d.upfront), 0)), activity: act.map((a) => ({ text: a.summary, at: a.created_at, who: nm[a.employee_id] || "" })), fetched: new Date().toLocaleTimeString([], { hour12: false }) };
        st.teamCache = out; LS.set("lf_team", out); return out;
      } catch (e) {
        if (e instanceof Offline) { if (st.teamCache) return { ...st.teamCache, stale: true }; return fail("You're offline and the team numbers have not been loaded yet."); }
        if (e instanceof AuthLost) return fail("Signed out.");
        return fail("The shared database returned an error: " + String(e.message).slice(0, 140));
      }
    },
    // ----- animated pictures (5th migration)
    async upload_media(kind, dataUrl, thumb) {
      if (!["avatar", "banner"].includes(kind)) return { ok: false };
      if (!uid()) return fail("Sign in first.");
      const m = /^data:[\w/+.-]*;base64,([A-Za-z0-9+/=]+)$/.exec(String(dataUrl || ""));
      if (!m) return fail("That doesn't look like a picture.");
      let raw; try { raw = Uint8Array.from(atob(m[1]), (c) => c.charCodeAt(0)); } catch (e) { return fail("That picture is damaged."); }
      const lim = kind === "banner" ? 100 : 8;   // MB: banners up to 100 MB (11.9), profile pictures up to 8 MB
      if (raw.length > lim * 1024 * 1024) return fail(`That file is over ${lim} MB. Pick a smaller one.`);
      const mime = sniffImage(raw); if (!mime) return fail("Use a GIF, WebP, PNG, JPEG or AVIF image.");
      let t = String(thumb || ""); if (t && (!/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(t) || t.length > (kind === "avatar" ? 60000 : 150000))) t = "";
      return guardNet(async () => {
        if (st.caps.media == null) { try { await probe("avatar_url,banner_url,banner_pos", "profiles", "media"); } catch (e) { if (e instanceof Offline) throw e; } }
        if (!st.caps.media) return fail("Animated pictures need the 5th database update. Ask an admin to run it (see SETUP_SUPABASE.md).");
        const ext = { "image/gif": "gif", "image/webp": "webp", "image/png": "png", "image/jpeg": "jpg", "image/avif": "avif" }[mime];
        const path = `media/${uid()}/${kind}-${uuid4().replace(/-/g, "").slice(0, 12)}.${ext}`;
        const go = async (retry) => {
          let r; try { r = await fetch(SB + "/storage/v1/object/" + path, { method: "POST", headers: { apikey: KEY, Authorization: "Bearer " + (await token()), "Content-Type": mime, "cache-control": "31536000", "x-upsert": "false" }, body: raw }); }
          catch (e) { throw new Offline(String(e)); }
          if (r.status === 401 && retry) { await refresh(); return go(false); }
          if (!r.ok) throw new Http(r.status, await r.text());
        };
        await go(true);
        const url = SB + "/storage/v1/object/public/" + path, old = mediaOf()[kind + "_url"] || "", body = { [kind + "_url"]: url };
        if (t && kind === "avatar" && st.caps.avatar) body.avatar = t;
        if (t && kind === "banner" && st.caps.pext) body.banner = t;
        await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body, prefer: "return=minimal" });
        LS.set("lf_media", { ...mediaOf(), [kind + "_url"]: url }); if (t) LS.set(kind === "avatar" ? "lf_avatar" : "lf_banner", t);
        if (old.includes("/object/public/media/" + uid() + "/")) call("DELETE", "/storage/v1/object/media/" + old.split("/object/public/media/")[1]).catch(() => { });
        return { ok: true, url };
      });
    },
    async clear_media(kind) {
      if (!["avatar", "banner"].includes(kind)) return { ok: false };
      return guardNet(async () => {
        const old = mediaOf()[kind + "_url"] || "";
        if (st.caps.media) { await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body: { [kind + "_url"]: null }, prefer: "return=minimal" }); if (old) call("DELETE", "/storage/v1/object/media/" + old.split("/object/public/media/").pop()).catch(() => { }); }
        LS.set("lf_media", { ...mediaOf(), [kind + "_url"]: "" }); return { ok: true };
      });
    },
    async set_banner_pos(n) {
      n = Math.max(0, Math.min(100, parseInt(n, 10))); if (isNaN(n)) return { ok: false };
      LS.set("lf_media", { ...mediaOf(), banner_pos: n });
      if (st.caps.media) { try { await rest("PATCH", "profiles", { params: { id: "eq." + uid() }, body: { banner_pos: n }, prefer: "return=minimal" }); } catch (e) { return { ok: true, pending: true }; } }
      return { ok: true };
    },

    // ----- leaderboard data (ranking + badges are worked out by the page, same as the desktop app)
    async get_board() {
      if (!uid()) return fail("Sign in first.");
      try {
        const prof = await rest("GET", "profiles", { params: { select: pcols("id,username,display_name,role,active"), order: "display_name.asc" } });
        const stats = await call("POST", "/rest/v1/rpc/daily_stats", { body: { p_from: "2020-01-01", p_to: todayStr() } });
        const deals = await allPages("deals", { select: "owner_id,upfront,monthly,months,closed_at,first_bill" + (st.caps.paid ? ",confirmed" : ""), order: "closed_at.asc" });
        let tg = {}; try { const r = await rest("GET", "settings", { params: { key: "eq.daily_targets", select: "value" } }); tg = (r[0] && r[0].value) || {}; } catch (e) { if (!(e instanceof Http)) throw e; }
        const out = { ok: true, stale: false, today: todayStr(), people: prof.filter((p) => p.active).map(pub), stats, deals, targets: { calls: 100, connections: 20, meetings: 3, sales: 1, ...tg }, fetched: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) };
        LS.set("lf_board", out); return out;
      } catch (e) {
        if (e instanceof Offline) { const c = LS.get("lf_board", null); return c ? { ...c, stale: true } : fail("You're offline. The leaderboard needs a connection the first time."); }
        return fail("The shared database returned an error: " + String(e.message).slice(0, 140));
      }
    },

    // ----- who gets the credit for a lead / meeting / deal (6th migration)
    async get_credit(kind, id) {
      if (kind === "lead") { const l = st.leads.get(String(id)); return { ok: true, owner: (l && l.called_by) || null }; }
      const d = [...st.deals.values()].find((x) => String(x.id) === String(id)); if (!d) return { ok: false };
      return guardNet(async () => { const r = await rest("GET", "deals", { params: { id: "eq." + d.uuid, select: "owner_id" } }); return { ok: true, owner: (r[0] && r[0].owner_id) || null }; });
    },
    async set_credit(kind, id, to) {
      if (!["lead", "deal"].includes(kind) || !/^[0-9a-f-]{36}$/.test(String(to || ""))) return fail("Pick a teammate.");
      let rid = String(id);
      if (kind === "deal") { const d = [...st.deals.values()].find((x) => String(x.id) === String(id)); if (!d) return fail("Deal not found."); rid = d.uuid; }
      try { await call("POST", "/rest/v1/rpc/reassign_credit", { body: { p_kind: kind, p_id: rid, p_to: to } }); }
      catch (e) {
        if (e instanceof Offline) return fail("You're offline. Try again when you're connected.");
        if (e instanceof Http && (e.status === 404 || ["PGRST202", "42883"].includes(e.code))) return { ok: false, need_migration: true, error: "Moving credit needs the 6th database update. Ask an admin to run it (see SETUP_SUPABASE.md)." };
        return fail(String((e.body && e.body.message) || e.message).slice(0, 160));
      }
      if (kind === "lead") { const l = st.leads.get(rid); if (l) { l.called_by = to; saveCache(); } }
      LS.del("lf_board"); return { ok: true };
    },

    // ----- announcements & ideas
    async get_posts() {
      if (!uid()) return fail("Sign in first.");
      try {
        const ps = await rest("GET", "posts", { params: { select: "*", order: "created_at.desc", limit: 200 } });
        const ids = ps.map((p) => p.id).join(",");
        const cm = ps.length ? await rest("GET", "post_comments", { params: { select: "*", post_id: `in.(${ids})`, order: "created_at.asc" } }) : [];
        const rx = ps.length ? await rest("GET", "post_reactions", { params: { select: "post_id,user_id,emoji", post_id: `in.(${ids})` } }) : [];
        for (const p of ps) { p.comments = cm.filter((c) => c.post_id === p.id); p.reactions = {}; for (const x of rx) if (x.post_id === p.id) (p.reactions[x.emoji] = p.reactions[x.emoji] || []).push(x.user_id); }
        return { ok: true, posts: ps };
      } catch (e) {
        if (e instanceof Http && [400, 404].includes(e.status) && /42P01|PGRST20|posts/.test(JSON.stringify(e.body || e.message))) return { ok: false, need_migration: true, error: "The Announcements board needs the 5th database update." };
        if (e instanceof Offline) return { ok: false, offline: true, error: "You're offline. The board loads when you reconnect." };
        return fail(String(e.message).slice(0, 160));
      }
    },
    async save_post(d) {
      d = d && typeof d === "object" ? d : {};
      const title = String(d.title || "").split(/\s+/).filter(Boolean).join(" ").slice(0, 120), body = String(d.body || "").trim().slice(0, 4000), kind = ["announcement", "idea", "update"].includes(d.kind) ? d.kind : "announcement";
      if (!title) return fail("Give the post a title.");
      return guardNet(async () => {
        const got = d.id ? await rest("PATCH", "posts", { params: { id: "eq." + d.id }, body: { title, body, kind }, prefer: "return=representation" })
          : await rest("POST", "posts", { body: { title, body, kind, author_id: uid() }, prefer: "return=representation" });
        return { ok: !!got.length, post: got[0] || null };
      });
    },
    async post_op(op, pid, arg) {
      if (!["delete", "pin", "react", "comment", "uncomment", "recomment"].includes(op) || !/^[0-9a-f-]{36}$/.test(String(pid || ""))) return { ok: false };
      if (op === "react" && !["👍", "🔥", "💡", "🎉", "❤️"].includes(arg)) return { ok: false };
      if (op === "comment" || op === "recomment") { arg = String(arg || "").trim().slice(0, 1000); if (!arg) return fail("Write something first."); }
      const me = uid();
      return guardNet(async () => {
        if (op === "delete") await rest("DELETE", "posts", { params: { id: "eq." + pid } });
        else if (op === "pin") await rest("PATCH", "posts", { params: { id: "eq." + pid }, body: { pinned: !!arg }, prefer: "return=minimal" });
        else if (op === "react") {
          const q = { post_id: "eq." + pid, user_id: "eq." + me, emoji: "eq." + arg };
          const have = await rest("GET", "post_reactions", { params: { ...q, select: "emoji" } });
          if (have.length) await rest("DELETE", "post_reactions", { params: q }); else await rest("POST", "post_reactions", { body: { post_id: pid, user_id: me, emoji: arg }, prefer: "return=minimal" });
        }
        else if (op === "comment") await rest("POST", "post_comments", { body: { post_id: pid, author_id: me, body: arg }, prefer: "return=minimal" });
        else if (op === "uncomment") await rest("DELETE", "post_comments", { params: { id: "eq." + pid } });
        else if (op === "recomment") await rest("PATCH", "post_comments", { params: { id: "eq." + pid }, body: { body: arg }, prefer: "return=minimal" });
        return { ok: true };
      });
    },
    async admin_people() {
      if (!isAdmin()) return fail("Administrators only.");
      return guardNet(async () => { const people = await rest("GET", "profiles", { params: { select: "id,username,display_name,role,active,last_seen,must_change_password", order: "display_name.asc" } }); const t = await API.get_team(); return { ok: true, people, targets: (t && t.targets) || {} }; });
    },
    async admin_update(pid, role, active) {
      if (!isAdmin()) return fail("Administrators only."); if (pid === uid()) return fail("You can't change your own role or deactivate yourself here.");
      return guardNet(async () => { const body = {}; if (role === "admin" || role === "employee") body.role = role; if (active != null) body.active = !!active; if (Object.keys(body).length) await rest("PATCH", "profiles", { params: { id: "eq." + pid }, body, prefer: "return=minimal" }); return { ok: true }; });
    },
    async admin_targets(t) {
      if (!isAdmin()) return fail("Administrators only.");
      const v = {}; for (const k of ["calls", "connections", "meetings", "sales"]) { const n = parseInt((t || {})[k] || 0, 10); if (isNaN(n)) return fail("Targets must be whole numbers."); v[k] = Math.max(0, n); }
      return guardNet(async () => { await rest("POST", "settings", { params: { on_conflict: "key" }, body: { key: "daily_targets", value: v }, prefer: "resolution=merge-duplicates,return=minimal" }); return { ok: true, targets: v }; });
    },
    async admin_export() {
      if (!isAdmin()) return fail("Administrators only.");
      return guardNet(async () => {
        const files = [], stamp = todayStr();
        for (const [t, order] of [["leads", "id.asc"], ["call_log", "started_at.asc"], ["deals", "created_at.asc"], ["events", "day.asc"], ["profiles", "username.asc"]]) {
          let rows = await allPages(t, { select: "*", order });
          if (t === "profiles") rows = rows.map((r) => { const o = { ...r }; delete o.status_text; delete o.banner; delete o.avatar; return o; });
          const cols = []; rows.forEach((r) => Object.keys(r).forEach((k) => { if (!cols.includes(k)) cols.push(k); }));
          const name = `leafline_company_${stamp}_${t === "call_log" ? "calls" : t}.csv`;
          download(name, toCsv([cols, ...rows.map((r) => cols.map((c) => (r[c] && typeof r[c] === "object" ? JSON.stringify(r[c]) : r[c])))]));
          files.push({ file: name, rows: rows.length }); await new Promise((r) => setTimeout(r, 400));
        }
        return { ok: true, files, folder: "your Downloads folder" };
      });
    },
  };
  function sniffImage(b) {
    const s = (a, n) => String.fromCharCode(...b.slice(a, a + n));
    if (s(0, 6) === "GIF87a" || s(0, 6) === "GIF89a") return "image/gif";
    if (b[0] === 0x89 && s(1, 3) === "PNG") return "image/png";
    if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "image/jpeg";
    if (s(0, 4) === "RIFF" && s(8, 4) === "WEBP") return "image/webp";
    if (s(4, 4) === "ftyp" && ["avif", "avis"].includes(s(8, 4))) return "image/avif";
    return null;
  }
  function toCsv(table) { return "﻿" + table.map((r) => r.map((v) => { v = v == null ? "" : String(v); return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(",")).join("\r\n"); }
  function download(name, text) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000); }

  window.LF_API = async (name, ...args) => {
    const f = API[name];
    if (!f) throw new Error("Unknown action: " + name);
    return f(...args);
  };

  // ------------------------------------------------------------------ updates: the page is always the newest published one
  const listeners = [];
  const upd = { state: "idle", version: VERSION, latest: VERSION, error: "" };
  const say = (patch) => { Object.assign(upd, patch); listeners.forEach((f) => { try { f({ ...upd }); } catch (e) { } }); };
  async function checkVersion(auto) {
    say({ state: "checking", error: "" });
    try {
      const r = await fetch("version.json?ts=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json(), latest = String(j.version || ""), lb = String(j.build || j.version || "");
      if (!latest) throw new Error("bad version file");
      if (lb !== BUILD) {
        try { const reg = await navigator.serviceWorker.getRegistration(); if (reg) await reg.update(); } catch (e) { }
        say({ state: "ready", latest });
        const tried = sessionStorage.getItem("lf_reloaded");
        if (auto && tried !== latest) { sessionStorage.setItem("lf_reloaded", latest); setTimeout(() => location.reload(), 300); }
      } else say({ state: "none", latest });
    } catch (e) { say({ state: navigator.onLine ? "error" : "none", error: navigator.onLine ? "Couldn't check: " + String(e.message || e) : "" }); }
    return { ...upd };
  }
  window.LF_WEB = {
    platform: "web",
    appInfo: async () => ({ version: VERSION, platform: "web" }),
    checkUpdate: () => checkVersion(false),
    installUpdate: async () => { try { const keys = await caches.keys(); await Promise.all(keys.map((k) => caches.delete(k))); } catch (e) { } location.reload(); },
    onUpdate: (f) => { listeners.push(f); },
    status: () => ({ ...upd }),
  };
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("sw.js?v=" + encodeURIComponent(BUILD)).catch(() => { });
  }
  setTimeout(() => checkVersion(true), 1200);
  setInterval(() => { if (!document.hidden) checkVersion(false); }, 10 * 60 * 1000);
})();
