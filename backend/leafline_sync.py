"""Leafline <-> Supabase synchronisation.

The local SQLite file stays as a CACHE; Supabase is the source of truth.
  * SQLite triggers copy every local write to leads / deals / events into a persistent `outbox` table, whichever part
    of the app made it. A row leaves the outbox only after Supabase confirmed it. Offline = it simply waits.
  * A background thread pushes the outbox (back-off retry) and pulls remote changes every few seconds (polling).
  * Edits carry a version number. If someone else saved first, the two copies are merged field by field (3-way);
    a field changed on both sides keeps the newer edit and BOTH values are saved in `sync_conflicts`.
  * Inserts carry a client_op_id so a retry after a lost reply can never create a duplicate.
  * Only the PUBLISHABLE key is in the app (public by design; row level security protects the data).
"""
import json, os, re, sys, threading, time, uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "https://yvpmgmuthrmzievgdifw.supabase.co").rstrip("/")
PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "sb_publishable_6ssgQB4Z9D3lYtBtL3m8uA_B4w0fFiQ"
EMAIL_DOMAIN = os.environ.get("LEAFLINE_EMAIL_DOMAIN") or "leaflineweb.com"   # login handle only; no email is ever sent
TZ = ZoneInfo(os.environ.get("LEAFLINE_TZ") or "America/Toronto")
POLL = 4.0
NS = uuid.UUID("6f1e3d8a-5b0c-4c7e-9a52-1d3a7c0b9e11")
OUTCOME = {"orange": "no_answer", "red": "not_interested", "yellow": "interested", "green": "meeting_booked"}


class Offline(Exception): pass
class AuthLost(Exception): pass
class AuthFail(Exception): pass


class Http(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {str(body)[:200]}")
        self.status, self.body = status, body
        self.code = body.get("code") if isinstance(body, dict) else None


def email_for(username): return f"{username.strip().lower()}@{EMAIL_DOMAIN}"


# ------------------------------------------------------------------ value helpers
def to_iso(s):
    s = s.strip() if isinstance(s, str) else ""
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try: return datetime.strptime(s, f).replace(tzinfo=TZ).astimezone(timezone.utc).isoformat()
        except ValueError: pass
    return None


def from_iso(s):
    if not s: return ""
    d = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)
    return d.strftime("%Y-%m-%d %H:%M:%S" if d.second else "%Y-%m-%d %H:%M")


def nt(x):
    if not x: return None
    try: return datetime.fromisoformat(str(x).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError: return x


def day_or_none(s):
    s = s.strip() if isinstance(s, str) else ""
    try: datetime.strptime(s, "%Y-%m-%d"); return s
    except ValueError: return None


def digits10(p): return re.sub(r"\D", "", p or "")[-10:]
def num(x): return round(float(x or 0), 2)
def now_iso(): return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ table specs (local row <-> remote row)
LEAD_L = "id,name,phone,owner,rating,reviews,website,address,search,btype,hours,status,notes,enriched,added_at,called_at,meeting_at"
TS_FIELDS = {"added_at", "called_at", "meeting_at"}


def lead_out(r):
    d = dict(zip(LEAD_L.split(","), r))
    return {"id": d["id"], "name": d["name"] or "", "phone": d["phone"] or "", "owner_name": d["owner"] or "N/A",
            "rating": d["rating"] or "N/A", "reviews": d["reviews"] or "N/A", "website": d["website"] or "N/A",
            "address": d["address"] or "N/A", "search": d["search"], "btype": d["btype"] or "", "hours": d["hours"] or "",
            "status": d["status"] or "none", "notes": d["notes"] or "", "enriched": bool(d["enriched"]),
            "added_at": to_iso(d["added_at"]), "called_at": to_iso(d["called_at"]), "meeting_at": to_iso(d["meeting_at"])}


def lead_in(R):
    return {"id": R["id"], "name": R["name"], "phone": R["phone"], "owner": R["owner_name"], "rating": R["rating"],
            "reviews": R["reviews"], "website": R["website"], "address": R["address"], "search": R["search"],
            "btype": R["btype"], "hours": R["hours"], "status": R["status"], "notes": R["notes"],
            "enriched": 1 if R["enriched"] else 0, "added_at": from_iso(R["added_at"]),
            "called_at": from_iso(R["called_at"]) or None, "meeting_at": from_iso(R["meeting_at"])}


DEAL_L = "id,client,upfront,monthly,months,closed_at,first_bill,notes,created_at,confirmed"


def deal_out(r):
    d = dict(zip(DEAL_L.split(","), r))
    return {"id": d["id"], "client": d["client"] or "", "upfront": num(d["upfront"]), "monthly": num(d["monthly"]),
            "months": int(d["months"] or 0), "closed_at": day_or_none(d["closed_at"]), "first_bill": day_or_none(d["first_bill"]),
            "notes": d["notes"] or "", "confirmed": d["confirmed"] or ""}


def deal_in(R):
    return {"client": R["client"], "upfront": float(R["upfront"] or 0), "monthly": float(R["monthly"] or 0), "months": R["months"] or 0,
            "closed_at": R["closed_at"] or "", "first_bill": R["first_bill"] or "", "notes": R["notes"] or "",
            **({"confirmed": R["confirmed"] or ""} if "confirmed" in R else {})}


EVENT_L = "id,title,day,start_time,color,icon,repeat_kind,until,notes,lead_id,created_at,assigned_to,created_by,done,done_at"


def event_out(r):
    d = dict(zip(EVENT_L.split(","), r))
    return {"id": d["id"], "title": d["title"] or "", "day": day_or_none(d["day"]), "start_time": d["start_time"] or "",
            "color": d["color"] or "", "icon": d["icon"] or "", "repeat_kind": d["repeat_kind"] or "none",
            "until": day_or_none(d["until"]), "notes": d["notes"] or "", "lead_id": d["lead_id"] or None,
            "assigned_to": d["assigned_to"] or None, "created_by": d["created_by"] or None,
            "done": bool(d["done"]), "done_at": to_iso(d["done_at"]) if d["done"] else None}


def event_in(R):
    return {"title": R["title"], "day": R["day"], "start_time": R["start_time"] or "", "color": R["color"] or "", "icon": R["icon"] or "",
            "repeat_kind": R["repeat_kind"] or "none", "until": R["until"] or "", "notes": R["notes"] or "", "lead_id": R["lead_id"] or "",
            "assigned_to": R.get("assigned_to") or "", **({"created_by": R["created_by"] or ""} if "created_by" in R else {}),
            **({"done": 1 if R["done"] else 0, "done_at": from_iso(R.get("done_at")) if R["done"] else ""} if "done" in R else {})}


NOTE_L = "id,kind,scope,title,folder,body,owner_id,created_at"


def note_out(r):
    d = dict(zip(NOTE_L.split(","), r))
    return {"id": d["id"], "kind": d["kind"] or "note", "scope": d["scope"] or "personal", "title": d["title"] or "Untitled",
            "folder": d["folder"] or "", "body": d["body"] or "", "owner_id": d["owner_id"] or None}


def note_in(R):
    return {"kind": R["kind"] or "note", "scope": R["scope"] or "personal", "title": R["title"] or "Untitled",
            "folder": R["folder"] or "", "body": R["body"] or "", **({"owner_id": R["owner_id"] or ""} if "owner_id" in R else {})}


SPEC = {
    "leads": dict(cols=LEAD_L, out=lead_out, inn=lead_in, rank=0, keys=[k for k in lead_out((None,) * 17) if k != "id"]),
    "deals": dict(cols=DEAL_L, out=deal_out, inn=deal_in, rank=1, keys=[k for k in deal_out((None,) * 10) if k != "id"]),
    "events": dict(cols=EVENT_L, out=event_out, inn=event_in, rank=2, keys=[k for k in event_out((None,) * 15) if k not in ("id", "created_by")]),
    "notes": dict(cols=NOTE_L, out=note_out, inn=note_in, rank=3, keys=[k for k in note_out((None,) * 8) if k not in ("id", "owner_id")]),
}
OPTIONAL = {"events": ("done", ("done", "done_at")),     # columns that exist only after an optional migration (probed at runtime):
            "deals": ("paid", ("confirmed",))}             # table -> (capability, columns). done = 2nd migration, paid = 7th


def same(a, b, k=None):
    if k in TS_FIELDS: return nt(a) == nt(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) < 0.005
    return (a if a not in ("", None) else None) == (b if b not in ("", None) else None)


def merge3(base, local, remote, local_newer):
    """Per-field 3-way merge. Returns (merged, lost); lost lists fields changed on BOTH sides."""
    out, lost = {}, []
    for k, l in local.items():
        r, b = remote.get(k), (base or {}).get(k)
        if same(l, r, k): out[k] = l
        elif base is not None and same(l, b, k): out[k] = r
        elif base is not None and same(r, b, k): out[k] = l
        else:
            keep = local_newer and base is not None
            out[k] = l if keep else r
            lost.append({"field": k, "mine": l, "theirs": r, "kept": "mine" if keep else "theirs"})
    return out, lost


# ------------------------------------------------------------------ local schema
def ensure_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS sync_kv(k TEXT PRIMARY KEY, v TEXT);
    INSERT OR IGNORE INTO sync_kv(k,v) VALUES('applying','0');
    INSERT OR IGNORE INTO sync_kv(k,v) VALUES('uid','');
    CREATE TABLE IF NOT EXISTS sync_meta(tbl TEXT, local_id TEXT, remote_id TEXT DEFAULT '', version INTEGER DEFAULT 0,
        base TEXT DEFAULT '', aux TEXT DEFAULT '', op_id TEXT DEFAULT '', PRIMARY KEY(tbl, local_id));
    CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, tbl TEXT, local_id TEXT, op TEXT, actor TEXT DEFAULT '',
        queued_at TEXT, attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', blocked INTEGER DEFAULT 0, UNIQUE(tbl, local_id));
    CREATE TABLE IF NOT EXISTS sync_conflicts(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, tbl TEXT, local_id TEXT, kind TEXT,
        detail TEXT, seen INTEGER DEFAULT 0);
    """)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT DEFAULT 'note', scope TEXT DEFAULT 'personal',
        title TEXT DEFAULT 'Untitled', folder TEXT DEFAULT '', body TEXT DEFAULT '', owner_id TEXT DEFAULT '', created_at TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS call_queue(op_id TEXT PRIMARY KEY, payload TEXT, actor TEXT DEFAULT '', queued_at TEXT,
        attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', blocked INTEGER DEFAULT 0);
    """)
    cols = {r[1] for r in db.execute("PRAGMA table_info(events)")}
    for c, typ in (("assigned_to", "TEXT"), ("created_by", "TEXT"), ("done", "INTEGER"), ("done_at", "TEXT")):   # upgrade the cache in place
        if c not in cols: db.execute(f"ALTER TABLE events ADD COLUMN {c} {typ} DEFAULT {'0' if typ == 'INTEGER' else chr(39)*2}")
    when = "WHEN (SELECT v FROM sync_kv WHERE k='applying')='0'"
    for t in SPEC:
        for name, ev, ref, op in (("ai", "INSERT", "NEW", "upsert"), ("au", "UPDATE", "NEW", "upsert"), ("ad", "DELETE", "OLD", "delete")):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS sy_{t}_{name} AFTER {ev} ON {t} {when} BEGIN
                INSERT OR REPLACE INTO outbox(tbl,local_id,op,actor,queued_at)
                VALUES('{t}', CAST({ref}.id AS TEXT), '{op}', (SELECT v FROM sync_kv WHERE k='uid'), strftime('%Y-%m-%dT%H:%M:%fZ','now')); END""")
    db.commit()


# ------------------------------------------------------------------ session storage + auth
def _dpapi(data, decrypt=False):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    inb, out = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(inb), None, None, None, None, 0, ctypes.byref(out)): raise OSError("DPAPI failed")
    try: return ctypes.string_at(out.pbData, out.cbData)
    finally: ctypes.windll.kernel32.LocalFree(out.pbData)


class Auth:
    """Session tokens are stored encrypted for this Windows user (DPAPI); never the password."""
    def __init__(self, path):
        self.path, self.s, self.lock = path, None, threading.RLock()
        try:
            raw = open(path, "rb").read()
            if raw[:4] == b"DPA1": raw = _dpapi(raw[4:], True)
            self.s = json.loads(raw.decode())
        except Exception:
            self.s = None   # unreadable = sign in again; local data is untouched

    def _save(self):
        raw = json.dumps(self.s).encode()
        if sys.platform == "win32":
            try: raw = b"DPA1" + _dpapi(raw)
            except Exception: pass
        with open(self.path, "wb") as fh: fh.write(raw)
        try: os.chmod(self.path, 0o600)
        except OSError: pass

    def clear(self):
        self.s = None
        try: os.remove(self.path)
        except OSError: pass

    def _take(self, r):
        j = r.json()
        self.s = {"access_token": j["access_token"], "refresh_token": j["refresh_token"],
                  "expires_at": time.time() + int(j.get("expires_in", 3600)), "uid": j["user"]["id"]}
        self._save()

    def _post(self, grant, body):
        try:
            return requests.post(SUPABASE_URL + "/auth/v1/token", params={"grant_type": grant}, json=body, timeout=25,
                                 headers={"apikey": PUBLISHABLE_KEY, "Content-Type": "application/json"})
        except (requests.ConnectionError, requests.Timeout) as e:
            raise Offline(str(e))

    def login(self, username, password):
        with self.lock:
            r = self._post("password", {"email": email_for(username), "password": password})
            if r.status_code in (400, 401, 403, 422): raise AuthFail("Wrong username or password.")
            if r.status_code >= 400: raise Http(r.status_code, r.text)
            self._take(r)

    def refresh(self):
        with self.lock:
            if not self.s: raise AuthLost()
            r = self._post("refresh_token", {"refresh_token": self.s["refresh_token"]})
            if r.status_code in (400, 401, 403): raise AuthLost()
            if r.status_code >= 400: raise Http(r.status_code, r.text)
            self._take(r)

    def token(self):
        with self.lock:
            if not self.s: raise AuthLost()
            if self.s["expires_at"] - 60 < time.time(): self.refresh()
            return self.s["access_token"]

    def uid(self): return (self.s or {}).get("uid", "")


class Remote:
    def __init__(self, auth): self.auth = auth

    def call(self, method, path, params=None, body=None, prefer=None, retry=True):
        h = {"apikey": PUBLISHABLE_KEY, "Authorization": "Bearer " + self.auth.token(), "Content-Type": "application/json"}
        if prefer: h["Prefer"] = prefer
        try:
            r = requests.request(method, SUPABASE_URL + path, params=params, headers=h, timeout=(5, 30),
                                 data=json.dumps(body) if body is not None else None)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise Offline(str(e))
        if r.status_code == 401 and retry:
            self.auth.refresh()
            return self.call(method, path, params, body, prefer, False)
        if r.status_code >= 400:
            try: b = r.json()
            except ValueError: b = r.text
            raise Http(r.status_code, b)
        try: return r.json() if r.content else []
        except ValueError: return []

    def rest(self, method, table, **kw): return self.call(method, "/rest/v1/" + table, **kw)

    def upload(self, path, data, mime, retry=True):
        """Raw file into Supabase Storage (bucket/path). Returns the public URL."""
        h = {"apikey": PUBLISHABLE_KEY, "Authorization": "Bearer " + self.auth.token(), "Content-Type": mime, "cache-control": "31536000", "x-upsert": "false"}
        try:
            r = requests.post(SUPABASE_URL + "/storage/v1/object/" + path, headers=h, data=data, timeout=(5, 60))
        except (requests.ConnectionError, requests.Timeout) as e:
            raise Offline(str(e))
        if r.status_code == 401 and retry:
            self.auth.refresh(); return self.upload(path, data, mime, False)
        if r.status_code >= 400:
            try: b = r.json()
            except ValueError: b = r.text
            raise Http(r.status_code, b)
        return SUPABASE_URL + "/storage/v1/object/public/" + path

    def remove(self, path):
        try: self.call("DELETE", "/storage/v1/object/" + path)
        except (Http, Offline): pass

    def all_pages(self, table, params, page=1000):
        out, off = [], 0
        while True:
            rows = self.rest("GET", table, params={**params, "limit": page, "offset": off})
            out += rows
            if len(rows) < page: return out
            off += page


# ------------------------------------------------------------------ engine
class Sync:
    def __init__(self, db, lock, emit, data_dir):
        self.db, self.lock, self.emit = db, lock, emit
        self.auth = Auth(os.path.join(data_dir, "session.json"))
        self.remote = Remote(self.auth)
        self.profile = None
        self.status = {"state": "signed_out", "pending": 0, "blocked": 0, "conflicts": 0, "last_ok": None, "error": ""}
        self.stop, self.wake, self.push_lock = threading.Event(), threading.Event(), threading.Lock()
        self.first, self.last_beat, self.last_recon, self._t = True, 0.0, 0.0, None
        self.caps = {"done": None, "avatar": None, "pext": None, "media": None, "paid": None}          # None = not probed yet
        with self.lock: ensure_schema(self.db)

    # ---- lifecycle
    def start(self):
        if self._t is None:
            self._t = threading.Thread(target=self._loop, daemon=True); self._t.start()
            threading.Thread(target=self._beat_loop, daemon=True).start()

    def _beat_loop(self):
        """'Online' heartbeat every 30 s on its own, so a slow or failing sync can never make someone look offline."""
        while not self.stop.is_set():
            try:
                if self.auth.uid():
                    self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()},
                                     body={"last_seen": now_iso(), "status_text": "Online"}, prefer="return=minimal")
            except Exception: pass
            self.stop.wait(30)

    def kick(self): self.wake.set()

    def keys(self, t):
        ks = SPEC[t]["keys"]
        if t in OPTIONAL and not self.caps.get(OPTIONAL[t][0]): ks = [k for k in ks if k not in OPTIONAL[t][1]]
        return ks

    def probe_avatar(self):
        try:
            self.remote.rest("GET", "profiles", params={"select": "avatar", "limit": 1}); self.caps["avatar"] = True
        except Http as e:
            if e.status in (400, 404): self.caps["avatar"] = False
            else: raise

    PEXT = ("title", "bio", "thought", "thought_at", "mood", "accent")      # small profile extras (migration 4); the banner is fetched separately

    def probe_pext(self):
        try:
            self.remote.rest("GET", "profiles", params={"select": "bio,thought,thought_at,title,mood,accent,banner", "limit": 1}); self.caps["pext"] = True
        except Http as e:
            if e.status in (400, 404): self.caps["pext"] = False
            else: raise

    MEDIA = ("avatar_url", "banner_url", "banner_pos")                       # animated pictures (migration 5)

    def probe_media(self):
        try:
            self.remote.rest("GET", "profiles", params={"select": ",".join(self.MEDIA), "limit": 1}); self.caps["media"] = True
        except Http as e:
            if e.status in (400, 404): self.caps["media"] = False
            else: raise

    def pcols(self, base):
        return (base + (",avatar" if self.caps.get("avatar") else "") + ("," + ",".join(self.PEXT) if self.caps.get("pext") else "")
                + ("," + ",".join(self.MEDIA) if self.caps.get("media") else ""))

    def media(self):
        try: m = json.loads(self._kv("media") or "{}")
        except ValueError: m = {}
        return {k: (m or {}).get(k) or ("" if k != "banner_pos" else 50) for k in self.MEDIA}

    MIME = {"image/gif": "gif", "image/webp": "webp", "image/png": "png", "image/jpeg": "jpg", "image/avif": "avif"}

    def upload_media(self, kind, data, mime, thumb=None):
        """kind = avatar | banner. The original file (animation kept) goes to Storage; a small still copy stays in the row."""
        if self.caps.get("media") is None:
            try: self.probe_media()
            except Http: pass
        if not self.caps.get("media"): return dict(ok=False, error="Animated pictures need the 5th database update. Ask an admin to run it (see SETUP_SUPABASE.md).")
        uid = self.auth.uid(); name = f"{uid}/{kind}-{uuid.uuid4().hex[:12]}.{self.MIME[mime]}"
        url = self.remote.upload("media/" + name, data, mime)
        old = self.media().get(kind + "_url") or ""
        body = {kind + "_url": url}
        if kind == "avatar" and thumb and self.caps.get("avatar"): body["avatar"] = thumb
        if kind == "banner" and thumb and self.caps.get("pext"): body["banner"] = thumb
        self.remote.rest("PATCH", "profiles", params={"id": "eq." + uid}, body=body, prefer="return=minimal")
        m = self.media(); m[kind + "_url"] = url; self._kv("media", json.dumps(m))
        if kind == "avatar" and thumb: self._kv("avatar", thumb)
        if kind == "banner" and thumb: self._kv("banner", thumb)
        if "/object/public/media/" + uid + "/" in old: self.remote.remove("media/" + old.split("/object/public/media/", 1)[1])
        return dict(ok=True, url=url)

    def clear_media(self, kind):
        m = self.media(); old = m.get(kind + "_url") or ""
        if self.caps.get("media"):
            self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()}, body={kind + "_url": None}, prefer="return=minimal")
            if old: self.remote.remove("media/" + old.split("/object/public/media/", 1)[-1])
        m[kind + "_url"] = ""; self._kv("media", json.dumps(m))
        return dict(ok=True)

    def set_banner_pos(self, n):
        m = self.media(); m["banner_pos"] = n; self._kv("media", json.dumps(m))
        if self.caps.get("media"):
            self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()}, body={"banner_pos": n}, prefer="return=minimal")
        return dict(ok=True)

    # ---- leaderboard data (the page does the ranking, so desktop and website rank identically)
    def board(self):
        try:
            prof = self.remote.rest("GET", "profiles", params={"select": self.pcols("id,username,display_name,role,active"), "order": "display_name.asc"})
            today = datetime.now(TZ).date().isoformat()
            stats = self.remote.call("POST", "/rest/v1/rpc/daily_stats", body={"p_from": "2020-01-01", "p_to": today})
            deals = self.remote.all_pages("deals", {"select": "owner_id,upfront,monthly,months,closed_at,first_bill" + (",confirmed" if self.caps.get("paid") else ""), "order": "closed_at.asc"})
            try: tg = (self.remote.rest("GET", "settings", params={"key": "eq.daily_targets", "select": "value"}) or [{}])[0].get("value") or {}
            except Http: tg = {}
            out = dict(ok=True, stale=False, today=today, people=[self._pub(p) for p in prof if p.get("active")], stats=stats, deals=deals,
                       targets={"calls": 100, "connections": 20, "meetings": 3, "sales": 1, **tg},
                       fetched=datetime.now().strftime("%H:%M"))
            self._kv("board", json.dumps(out))
            return out
        except Offline:
            try: c = json.loads(self._kv("board") or "null")
            except ValueError: c = None
            return dict(c, stale=True) if c else dict(ok=False, error="You're offline. The leaderboard needs a connection the first time.")

    def _pub(self, p):
        return dict(id=p["id"], name=p.get("display_name") or p.get("username"), role=p.get("role"), avatar=p.get("avatar") or "",
                    ext={k: p.get(k) or "" for k in self.PEXT}, media={k: p.get(k) for k in self.MEDIA if p.get(k) is not None})

    # ---- who gets the credit for a lead / meeting / deal (migration 6)
    def remote_id(self, t, lid):
        with self.lock:
            r = self.db.execute("SELECT remote_id FROM sync_meta WHERE tbl=? AND local_id=?", (t, str(lid))).fetchone()
        return r[0] if r and r[0] else None

    def get_credit(self, kind, lid):
        if kind == "lead": return self.callers().get(str(lid)) or None
        rid = self.remote_id("deals", lid)
        if not rid: return None
        rows = self.remote.rest("GET", "deals", params={"id": "eq." + rid, "select": "owner_id"})
        return rows[0]["owner_id"] if rows else None

    def set_credit(self, kind, lid, to):
        rid = str(lid) if kind == "lead" else self.remote_id("deals", lid)
        if not rid: return dict(ok=False, error="This deal hasn't reached the shared database yet. Wait for Synced and try again.")
        try:
            self.remote.call("POST", "/rest/v1/rpc/reassign_credit", body={"p_kind": kind, "p_id": rid, "p_to": to})
        except Http as e:
            b = e.body if isinstance(e.body, dict) else {}
            if e.status == 404 or b.get("code") in ("PGRST202", "42883"):
                return dict(ok=False, need_migration=True, error="Moving credit needs the 6th database update. Ask an admin to run it (see SETUP_SUPABASE.md).")
            return dict(ok=False, error=str(b.get("message") or e)[:160])
        if kind == "lead":
            c = self.callers(); c[str(lid)] = to; self._kv("callers", json.dumps(c))
        self._kv("board", ""); self.emit("refresh", {})
        return dict(ok=True)

    # ---- announcements & ideas (online, straight from the shared database)
    def _need5(self, e):
        b = e.body if isinstance(e.body, dict) else {}
        return e.status in (400, 404) and (b.get("code") in ("42P01", "PGRST205", "PGRST200") or "posts" in str(b))

    def posts(self):
        try:
            ps = self.remote.rest("GET", "posts", params={"select": "*", "order": "created_at.desc", "limit": 200})
            ids = ",".join(p["id"] for p in ps)
            cm = self.remote.rest("GET", "post_comments", params={"select": "*", "post_id": f"in.({ids})", "order": "created_at.asc"}) if ps else []
            rx = self.remote.rest("GET", "post_reactions", params={"select": "post_id,user_id,emoji", "post_id": f"in.({ids})"}) if ps else []
        except Http as e:
            if self._need5(e): return dict(ok=False, need_migration=True, error="The Announcements board needs the 5th database update.")
            raise
        for p in ps:
            p["comments"] = [c for c in cm if c["post_id"] == p["id"]]
            r = {}
            for x in rx:
                if x["post_id"] == p["id"]: r.setdefault(x["emoji"], []).append(x["user_id"])
            p["reactions"] = r
        return dict(ok=True, posts=ps)

    def save_post(self, d):
        body = {k: d[k] for k in ("kind", "title", "body") if k in d}
        if d.get("id"):
            got = self.remote.rest("PATCH", "posts", params={"id": "eq." + d["id"]}, body=body, prefer="return=representation")
        else:
            body["author_id"] = self.auth.uid()
            got = self.remote.rest("POST", "posts", body=body, prefer="return=representation")
        return dict(ok=bool(got), post=got[0] if got else None)

    def post_op(self, op, pid, arg=None):
        uid = self.auth.uid()
        if op == "delete": self.remote.rest("DELETE", "posts", params={"id": "eq." + pid})
        elif op == "pin": self.remote.rest("PATCH", "posts", params={"id": "eq." + pid}, body={"pinned": bool(arg)}, prefer="return=minimal")
        elif op == "react":
            have = self.remote.rest("GET", "post_reactions", params={"post_id": "eq." + pid, "user_id": "eq." + uid, "emoji": "eq." + arg, "select": "emoji"})
            if have: self.remote.rest("DELETE", "post_reactions", params={"post_id": "eq." + pid, "user_id": "eq." + uid, "emoji": "eq." + arg})
            else: self.remote.rest("POST", "post_reactions", body={"post_id": pid, "user_id": uid, "emoji": arg}, prefer="return=minimal")
        elif op == "comment": self.remote.rest("POST", "post_comments", body={"post_id": pid, "author_id": uid, "body": arg}, prefer="return=minimal")
        elif op == "uncomment": self.remote.rest("DELETE", "post_comments", params={"id": "eq." + pid})
        elif op == "recomment": self.remote.rest("PATCH", "post_comments", params={"id": "eq." + pid}, body={"body": arg}, prefer="return=minimal")
        return dict(ok=True)

    def ext(self):
        """Own profile extras as the page shows them (works offline: kept in the local cache)."""
        try: e = json.loads(self._kv("pext") or "{}")
        except ValueError: e = {}
        return {**{k: "" for k in self.PEXT}, **(e if isinstance(e, dict) else {}), "banner": self._kv("banner") or ""}

    def set_ext(self, d):
        """Saved on this computer at once, uploaded as soon as the shared database can take it."""
        banner = d.pop("banner", None)
        cur = self.ext(); cur.pop("banner", None)
        cur.update({k: d[k] for k in self.PEXT if k in d})
        if "thought" in d and d["thought"] != self.ext().get("thought"): cur["thought_at"] = now_iso() if d["thought"] else ""
        self._kv("pext", json.dumps(cur))
        if banner is not None: self._kv("banner", banner)
        self._kv("pext_pending", "1"); self.kick()

    def _push_ext(self):
        if self._kv("pext_pending") != "1" or not self.caps.get("pext"): return
        e = self.ext(); body = {k: (e.get(k) or None) for k in self.PEXT}; body["banner"] = e.get("banner") or None
        self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()}, body=body, prefer="return=minimal")
        self._kv("pext_pending", "0")

    def person(self, pid):
        """Another person's full card (with banner). Needs a connection."""
        rows = self.remote.rest("GET", "profiles", params={"id": "eq." + pid, "select": self.pcols("id,username,display_name,role,active,last_seen") + (",banner" if self.caps.get("pext") else "")})
        return rows[0] if rows else None

    def probe(self):
        """The optional 2nd migration adds events.done. Until it is run, those fields stay local and nothing breaks."""
        try:
            self.remote.rest("GET", "events", params={"select": "done,done_at", "limit": 1})
            if not self.caps.get("done"):
                # first time the server can take it: ticks made while it could not are queued now, never dropped
                with self.lock:
                    self.db.execute("""INSERT OR IGNORE INTO outbox(tbl,local_id,op,actor,queued_at)
                        SELECT 'events', CAST(id AS TEXT), 'upsert', '', strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM events WHERE done=1""")
                    self.db.commit()
            self.caps["done"] = True
        except Http as e:
            if e.status in (400, 404): self.caps["done"] = False
            else: raise

    def probe_paid(self):
        """The 7th migration adds deals.confirmed (payments ticked as received). Before it is run, ticks stay on this computer."""
        try:
            self.remote.rest("GET", "deals", params={"select": "confirmed", "limit": 1})
            if not self.caps.get("paid"):
                with self.lock:
                    self.db.execute("""INSERT OR IGNORE INTO outbox(tbl,local_id,op,actor,queued_at)
                        SELECT 'deals', CAST(id AS TEXT), 'upsert', '', strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM deals WHERE confirmed!=''""")
                    self.db.commit()
            self.caps["paid"] = True
        except Http as e:
            if e.status in (400, 404): self.caps["paid"] = False
            else: raise

    # ---- Messages (11.4): the page calls the msg_* database functions and the private file bucket through here.
    #      Only those: nothing else in the database can be reached this way. All rules are enforced by the database.
    MSG_FN = re.compile(r"^msg_[a-z_]{2,40}$")
    MSG_PATH = re.compile(r"^[0-9a-f-]{36}/[0-9a-f-]{36}/[A-Za-z0-9._-]{1,180}$")

    @staticmethod
    def _err(e):
        if isinstance(e, Offline): return dict(ok=False, offline=True, error="You're offline.")
        if isinstance(e, (AuthLost, AuthFail)): return dict(ok=False, error="Signed out.")
        if isinstance(e, Http):
            b = e.body if isinstance(e.body, dict) else {}
            if e.status == 404 and (b.get("code") in ("PGRST202", "42883") or "Could not find" in str(b)):
                return dict(ok=False, missing=True, error="Messages need the 8th database update. Ask an admin to run it (see SETUP_SUPABASE.md).")
            return dict(ok=False, status=e.status, error=str(b.get("message") or b.get("error") or e.body)[:300])
        return dict(ok=False, error=str(e)[:300])

    def msg_rpc(self, fn, args):
        if not isinstance(fn, str) or not self.MSG_FN.match(fn) or not isinstance(args, dict):
            return dict(ok=False, error="Not allowed.")
        try: return dict(ok=True, data=self.remote.call("POST", "/rest/v1/rpc/" + fn, body=args))
        except Exception as e: return self._err(e)

    def msg_storage(self, op, paths, opts=None):
        paths = paths if isinstance(paths, list) else [paths]
        if not paths or len(paths) > 100 or not all(isinstance(x, str) and self.MSG_PATH.match(x) for x in paths):
            return dict(ok=False, error="Not allowed.")
        base = SUPABASE_URL + "/storage/v1"
        try:
            if op == "sign_upload":
                r = self.remote.call("POST", "/storage/v1/object/upload/sign/message-files/" + paths[0], body={})
                return dict(ok=True, url=base + r["url"])
            if op == "sign":
                exp = max(60, min(int((opts or {}).get("expires") or 3600), 86400))
                r = self.remote.call("POST", "/storage/v1/object/sign/message-files", body={"expiresIn": exp, "paths": paths})
                return dict(ok=True, urls={x.get("path"): (base + x["signedURL"]) if x.get("signedURL") else None for x in (r or [])})
            if op == "remove":
                self.remote.call("DELETE", "/storage/v1/object/message-files", body={"prefixes": paths})
                return dict(ok=True)
        except Exception as e:
            return self._err(e)
        return dict(ok=False, error="Not allowed.")

    def msg_group_picture(self, data_url):
        """A group chat picture: a small image in the public 'media' bucket, in the uploader's own folder."""
        m = re.match(r"^data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$", str(data_url or ""))
        if not m: return dict(ok=False, error="Pick a JPG, PNG or WebP picture.")
        import base64
        raw = base64.b64decode(m.group(2))
        if len(raw) > 400_000: return dict(ok=False, error="That picture is too big.")
        try:
            url = self.remote.upload(f"media/{self.auth.uid()}/group-{uuid.uuid4().hex[:12]}.{'jpg' if m.group(1) == 'jpeg' else m.group(1)}", raw, "image/" + m.group(1))
            return dict(ok=True, url=url)
        except Exception as e:
            return self._err(e)

    def session_info(self):
        """For the page's own live connection (Supabase Realtime). Uses this person's own sign-in, never a secret key."""
        try: tok = self.auth.token()
        except Exception as e: return self._err(e)
        rt = os.environ.get("LEAFLINE_REALTIME_URL") or (SUPABASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/realtime/v1/websocket")
        return dict(ok=True, url=SUPABASE_URL, key=PUBLISHABLE_KEY, token=tok, uid=self.auth.uid(), realtime=rt)

    def _kv(self, k, v=None):
        with self.lock:
            if v is None:
                r = self.db.execute("SELECT v FROM sync_kv WHERE k=?", (k,)).fetchone()
                return r[0] if r else None
            self.db.execute("INSERT OR REPLACE INTO sync_kv(k,v) VALUES(?,?)", (k, v)); self.db.commit()

    def _counts(self):
        with self.lock:
            p = self.db.execute("SELECT COUNT(*) FROM outbox WHERE blocked=0").fetchone()[0] + self.db.execute("SELECT COUNT(*) FROM call_queue WHERE blocked=0").fetchone()[0]
            b = self.db.execute("SELECT COUNT(*) FROM outbox WHERE blocked=1").fetchone()[0] + self.db.execute("SELECT COUNT(*) FROM call_queue WHERE blocked=1").fetchone()[0]
            c = self.db.execute("SELECT COUNT(*) FROM sync_conflicts WHERE seen=0").fetchone()[0]
        return p, b, c

    def _state(self, state, err=""):
        p, b, c = self._counts()
        st = dict(self.status, state=state, pending=p, blocked=b, conflicts=c, error=err)
        if state == "synced": st["last_ok"] = datetime.now().strftime("%H:%M:%S")
        if st != self.status:
            self.status = st
            self.emit("sync", st)

    def conflict(self, t, lid, kind, detail, seen=0):
        with self.lock:
            self.db.execute("INSERT INTO sync_conflicts(at,tbl,local_id,kind,detail,seen) VALUES(?,?,?,?,?,?)",
                            (datetime.now().isoformat(timespec="seconds"), t, str(lid), kind, json.dumps(detail, default=str)[:20000], seen))
            self.db.commit()

    # ---- session API used by the page
    def me(self):
        if not self.auth.s: return None
        if self.profile: m = {k: self.profile.get(k) for k in ("id", "username", "display_name", "role", "must_change_password")}
        else:
            c = self._kv("me")               # offline start: the last known identity from this computer
            try: m = json.loads(c) if c else None
            except ValueError: m = None
        if m is not None:
            m["avatar"] = self._kv("avatar") or ""
            m["ext"] = self.ext()
            m["media"] = self.media()
        return m

    def sign_in(self, username, password):
        self.auth.login(username, password)
        uid = self.auth.uid()
        try: prof = self.fetch_profile()
        except Exception:
            self.auth.clear(); raise
        if not prof.get("active", False):
            self.auth.clear(); raise AuthFail("This account has been deactivated. Ask an administrator.")
        with self.lock:
            other = [r[0] for r in self.db.execute("SELECT actor FROM outbox WHERE actor!='' AND actor!=? UNION SELECT actor FROM call_queue WHERE actor!='' AND actor!=?", (uid, uid))]
        if other and prof.get("role") != "admin":
            self.auth.clear(); self.profile = None
            raise AuthFail("This computer still holds unsynced changes made by another employee. They must sign in and finish syncing first.")
        self._kv("uid", uid); self.first = True; self.kick()
        return self.me()

    def fetch_profile(self):
        rows = self.remote.rest("GET", "profiles", params={"id": "eq." + self.auth.uid(), "select": "*"})
        if not rows: raise AuthFail("No Leafline profile exists for this login. Ask an administrator.")
        self.profile = rows[0]
        if "avatar" in rows[0] and self._kv("avatar_pending") != "1": self._kv("avatar", rows[0].get("avatar") or "")
        if "bio" in rows[0] and self._kv("pext_pending") != "1":
            self._kv("pext", json.dumps({k: rows[0].get(k) or "" for k in self.PEXT})); self._kv("banner", rows[0].get("banner") or "")
        if "avatar_url" in rows[0]: self._kv("media", json.dumps({k: rows[0].get(k) for k in self.MEDIA}))
        self._kv("me", json.dumps({k: self.profile.get(k) for k in ("id", "username", "display_name", "role", "must_change_password")}))
        return self.profile

    def restore(self):
        """On app start: a saved session signs in silently. Starting offline still works from the local cache."""
        if not self.auth.s: return None
        try: self.fetch_profile()
        except (AuthLost, AuthFail): self.auth.clear(); return None
        except (Offline, Http): pass
        if self.profile is not None and not self.profile.get("active", True): self.auth.clear(); return None
        if self.auth.s and not self._kv("me"): self.auth.clear(); return None      # session we cannot identify: sign in again
        self._kv("uid", self.auth.uid())
        return self.me()

    def set_avatar(self, data_url):
        """Own picture: kept on this computer at once, uploaded as soon as the shared database can take it."""
        self._kv("avatar", data_url or ""); self._kv("avatar_pending", "1"); self.kick()

    def _push_avatar(self):
        if self._kv("avatar_pending") != "1" or not self.caps.get("avatar"): return
        self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()}, body={"avatar": self._kv("avatar") or None}, prefer="return=minimal")
        self._kv("avatar_pending", "0")

    def sign_out(self):
        try: self._push_locked()
        except Exception: pass
        p, b, _ = self._counts()
        if self._kv("avatar_pending") == "1" and self.caps.get("avatar"): p += 1
        if self._kv("pext_pending") == "1" and self.caps.get("pext"): p += 1
        if p + b: return {"ok": False, "pending": p + b}
        try: requests.post(SUPABASE_URL + "/auth/v1/logout", params={"scope": "local"}, timeout=8,
                           headers={"apikey": PUBLISHABLE_KEY, "Authorization": "Bearer " + self.auth.s["access_token"]})
        except Exception: pass
        self.force_sign_out()
        return {"ok": True}

    def force_sign_out(self):
        self.auth.clear(); self.profile = None; self._kv("uid", ""); self._kv("me", ""); self._kv("avatar", ""); self._kv("avatar_pending", "0")
        for k in ("pext", "banner"): self._kv(k, "")
        self._kv("pext_pending", "0"); self._state("signed_out")

    def change_password(self, new):
        self.remote.call("PUT", "/auth/v1/user", body={"password": new})
        self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()}, body={"must_change_password": False}, prefer="return=minimal")
        if self.profile:
            self.profile["must_change_password"] = False; self._kv("me", json.dumps(self.me()))

    def retry_blocked(self):
        with self.lock:
            self.db.execute("UPDATE outbox SET blocked=0, attempts=0, last_error=''")
            self.db.execute("UPDATE call_queue SET blocked=0, attempts=0, last_error=''"); self.db.commit()
        self.kick()

    def details(self):
        with self.lock:
            q = self.db.execute("SELECT tbl,local_id,op,attempts,last_error,blocked FROM outbox ORDER BY id LIMIT 50").fetchall()
            c = self.db.execute("SELECT id,at,tbl,kind,detail FROM sync_conflicts ORDER BY id DESC LIMIT 50").fetchall()
        return {"queue": [dict(zip(("table", "id", "op", "attempts", "error", "blocked"), r)) for r in q],
                "conflicts": [dict(zip(("id", "at", "table", "kind", "detail"), r)) for r in c]}

    def callers(self):
        try: return json.loads(self._kv("callers") or "{}")
        except ValueError: return {}

    def note_callers(self, ids, status):
        """Remember locally who made a call so the Called Leads page shows it at once (the server copy is refreshed every minute)."""
        c, me = self.callers(), self.auth.uid()
        for i in ids:
            if status == "none" or not me: c.pop(str(i), None)
            else: c[str(i)] = me
        self._kv("callers", json.dumps(c))

    def refresh_callers(self):
        got = self.remote.rest("GET", "leads", params={"select": "id,called_by", "called_by": "not.is.null", "limit": 20000})
        mine = {str(r["id"]): r["called_by"] for r in (got or []) if r.get("called_by")}
        with self.lock: pend = {r[0] for r in self.db.execute("SELECT local_id FROM outbox WHERE tbl='leads'")}
        old = self.callers()
        for k in pend:                       # a call still waiting to upload keeps its local caller
            if k in old: mine[k] = old[k]
        self._kv("callers", json.dumps(mine))

    def people(self):
        try: return json.loads(self._kv("people") or "[]")
        except ValueError: return []

    # ---- shared team dashboard (read-only, straight from the shared database)
    def team(self, days=14):
        """Live numbers for every employee. Offline: returns the last copy with stale=True (never invented)."""
        try:
            today = datetime.now(TZ).date()
            frm = today - timedelta(days=days - 1)
            prof = self.remote.rest("GET", "profiles", params={"select": self.pcols("id,username,display_name,role,active,last_seen"), "order": "display_name.asc"})
            stats = self.remote.call("POST", "/rest/v1/rpc/daily_stats", body={"p_from": frm.isoformat(), "p_to": today.isoformat()})
            act = self.remote.rest("GET", "activity", params={"select": "*", "order": "created_at.desc", "limit": 40})
            st = self.remote.rest("GET", "settings", params={"key": "eq.daily_targets", "select": "value"})
            deals = self.remote.rest("GET", "deals", params={"select": "upfront,closed_at,owner_id", "closed_at": "gte." + frm.isoformat()})
            tasks = {}
            if self.caps.get("done"):
                try:
                    since = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
                    for r in self.remote.rest("GET", "events", params={"select": "done_by", "done": "eq.true", "done_at": "gte." + since}):
                        tasks[r["done_by"]] = tasks.get(r["done_by"], 0) + 1
                except Http: pass
            self._kv("people", json.dumps([{k: p.get(k) for k in ("id", "username", "display_name", "role", "active", "avatar") + self.PEXT + self.MEDIA} for p in prof]))
            tg = (st[0]["value"] if st else {}) or {}
            targets = {"calls": 100, "connections": 20, "meetings": 3, "sales": 1, **tg}
            names = {p["id"]: p["display_name"] for p in prof}
            now = datetime.now(timezone.utc)
            def online(p):
                try: return (now - datetime.fromisoformat(p["last_seen"].replace("Z", "+00:00"))).total_seconds() < 120
                except Exception: return False
            zero = dict(calls=0, connections=0, prospects=0, meetings=0, sales=0)
            by = {}
            for r in stats:
                by.setdefault(r["day"], {})[r["employee_id"]] = {k: int(r[k] or 0) for k in zero}
            tdy = by.get(today.isoformat(), {})
            people = []
            for p in prof:
                if not p.get("active"): continue
                mine = dict(zero, **tdy.get(p["id"], {}))
                last = next((a for a in act if a["employee_id"] == p["id"]), None)
                per = dict(zero)
                for dd in by.values():
                    for k in zero: per[k] += dd.get(p["id"], {}).get(k, 0)
                people.append(dict(id=p["id"], name=p["display_name"], role=p["role"], avatar=p.get("avatar") or "", ext={k: p.get(k) or "" for k in self.PEXT}, media={k: p.get(k) for k in self.MEDIA if p.get(k) is not None}, online=online(p), today=dict(mine, tasks=tasks.get(p["id"], 0)), period=per,
                                   progress=round(100 * mine["calls"] / max(1, targets["calls"])),
                                   last=({"text": last["summary"], "at": last["created_at"]} if last else None)))
            unassigned = tdy.get(None)
            tot = dict(zero)
            for e in tdy.values():
                for k in zero: tot[k] += e[k]
            series = []
            for i in range(days):
                d = (frm + timedelta(days=i)).isoformat(); row = dict(zero)
                for e in by.get(d, {}).values():
                    for k in zero: row[k] += e[k]
                series.append(dict(day=d, **row))
            mon = today - timedelta(days=today.weekday())
            def wk(a, b):
                r = dict(zero)
                for x in series:
                    if a.isoformat() <= x["day"] <= b.isoformat():
                        for k in zero: r[k] += x[k]
                return r
            rev = sum(num(d["upfront"]) for d in deals if d["closed_at"] == today.isoformat())
            out = dict(ok=True, stale=False, tasks_enabled=bool(self.caps.get("done")), today=today.isoformat(), targets=targets, totals=tot, people=people, series=series,
                       week=wk(mon, today), last_week=wk(mon - timedelta(days=7), mon - timedelta(days=1)),
                       deals_today=sum(1 for d in deals if d["closed_at"] == today.isoformat()), revenue_today=round(rev, 2),
                       activity=[dict(text=a["summary"], at=a["created_at"], who=names.get(a["employee_id"], "")) for a in act],
                       fetched=datetime.now().strftime("%H:%M:%S"))
            self._kv("team_cache", json.dumps(out))
            return out
        except Offline:
            c = self._kv("team_cache")
            if c:
                o = json.loads(c); o["stale"] = True; return o
            return dict(ok=False, error="You're offline and the team numbers have not been loaded yet.")
        except AuthLost:
            return dict(ok=False, error="Signed out.")
        except Http as e:
            return dict(ok=False, error="The shared database returned an error: " + str(e)[:140])

    # ---- shared call log
    OUTCOMES = ("no_answer", "voicemail", "interested", "not_interested", "follow_up", "meeting_booked", "sale_completed")

    def calls(self, f):
        """Shared call log. Filters: employee, outcome, from, to (YYYY-MM-DD, local day), q (business / phone / notes)."""
        f = f or {}
        names = {p["id"]: p["display_name"] for p in self.people()}
        with self.lock:
            lead = {r[0]: (r[1], r[2]) for r in self.db.execute("SELECT id,name,phone FROM leads")}
            queued = [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM call_queue")]
        params = {"select": "*", "order": "started_at.desc"}
        and_ = []
        if f.get("employee"): params["employee_id"] = "is.null" if f["employee"] == "none" else "eq." + str(f["employee"])
        if f.get("outcome") in self.OUTCOMES: params["outcome"] = "eq." + f["outcome"]
        if f.get("from"):
            d = datetime.strptime(f["from"], "%Y-%m-%d").replace(tzinfo=TZ); and_.append("started_at.gte." + d.astimezone(timezone.utc).isoformat())
        if f.get("to"):
            d = datetime.strptime(f["to"], "%Y-%m-%d").replace(tzinfo=TZ) + timedelta(days=1); and_.append("started_at.lt." + d.astimezone(timezone.utc).isoformat())
        if and_: params["and"] = "(" + ",".join(and_) + ")"
        stale = False
        try:
            rows = self.remote.all_pages("call_log", params, page=1000) if f.get("q") else self.remote.rest("GET", "call_log", params={**params, "limit": 400})
        except Offline:
            c = self._kv("calls_cache"); rows = json.loads(c) if c else []; stale = True
        else:
            self._kv("calls_cache", json.dumps(rows[:400]))
        out = []
        for r in rows:
            nm, ph = lead.get(r.get("lead_id"), ("", ""))
            out.append(dict(id=r["id"], at=r["started_at"], who_id=r.get("employee_id"), who=names.get(r.get("employee_id"), "Unassigned"),
                            business=nm or "", phone=r.get("phone") or ph, outcome=r["outcome"], notes=r.get("notes") or "",
                            legacy=r.get("source") in ("legacy_status", "backfill"), pending=False))
        have = {r["id"] for r in out}
        for q in queued:                                     # waiting to sync: shown immediately, marked pending
            if f.get("employee") and q.get("employee_id") != f["employee"]: continue
            if f.get("outcome") and q.get("outcome") != f["outcome"]: continue
            nm, ph = lead.get(q.get("lead_id"), ("", ""))
            out.append(dict(id="q" + q["client_op_id"], at=q["started_at"], who_id=q.get("employee_id"), who=names.get(q.get("employee_id"), "Me"),
                            business=nm or q.get("business", ""), phone=q.get("phone") or ph, outcome=q["outcome"], notes=q.get("notes", ""),
                            legacy=False, pending=True))
        if f.get("q"):
            qq = f["q"].strip().lower(); dq = "" if re.search(r"[a-z]", qq) else re.sub(r"\D", "", qq)   # digits only match phone numbers
            out = [o for o in out if qq in o["business"].lower() or qq in (o["notes"] or "").lower() or (dq and dq in re.sub(r"\D", "", o["phone"] or ""))]
        out.sort(key=lambda o: o["at"] or "", reverse=True)
        return dict(ok=True, rows=out[:1000], stale=stale, capped=len(out) > 1000)

    # ---- administrator tools (all enforced again by row level security on the server)
    def admin_people(self):
        rows = self.remote.rest("GET", "profiles", params={"select": "id,username,display_name,role,active,last_seen,must_change_password", "order": "display_name.asc"})
        return rows

    def admin_update(self, pid, role=None, active=None):
        body = {}
        if role in ("admin", "employee"): body["role"] = role
        if active is not None: body["active"] = bool(active)
        if not body: return
        self.remote.rest("PATCH", "profiles", params={"id": "eq." + pid}, body=body, prefer="return=minimal")

    def admin_targets(self, t):
        t = {k: max(0, int(t.get(k, 0))) for k in ("calls", "connections", "meetings", "sales")}
        self.remote.rest("POST", "settings", params={"on_conflict": "key"}, prefer="resolution=merge-duplicates,return=minimal", body={"key": "daily_targets", "value": t})
        return t

    def admin_export(self, base):
        """Writes one CSV per table next to `base` (…_leads.csv, …_calls.csv …). Reads the shared database, not the local cache."""
        import csv
        base = re.sub(r"\.csv$", "", str(base), flags=re.I)
        files = []
        for t, order in (("leads", "id.asc"), ("call_log", "started_at.asc"), ("deals", "created_at.asc"), ("events", "day.asc"), ("profiles", "username.asc")):
            rows = self.remote.all_pages(t, {"select": "*", "order": order})
            if t == "profiles":
                rows = [{k: v for k, v in r.items() if k not in ("status_text",)} for r in rows]
            for r in rows:
                for k, v in list(r.items()):
                    if isinstance(v, (dict, list)): r[k] = json.dumps(v)
            cols = []
            for r in rows:
                for k in r:
                    if k not in cols: cols.append(k)
            path = f"{base}_{ {'call_log': 'calls'}.get(t, t)}.csv"
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
            files.append(dict(file=os.path.basename(path), rows=len(rows)))
        return files

    # ---- main loop
    def _loop(self):
        delay = POLL
        while not self.stop.is_set():
            try:
                if not self.auth.s: self._state("signed_out"); delay = 2
                else: self._cycle(); delay = 2 if self._counts()[0] else POLL
            except Offline as e:
                self._state("offline", str(e)[:120]); delay = min(max(delay * 2, 8), 60)
            except AuthLost:
                self.force_sign_out(); self.emit("auth_lost", {}); delay = 2
            except Exception as e:
                self._state("error", str(e)[:200]); delay = 15
            self.wake.wait(delay); self.wake.clear()

    def _cycle(self):
        if self.first or self._counts()[0]: self._state("syncing")
        if self.profile is None: self.fetch_profile()
        if not self.profile.get("active", True):
            self.force_sign_out(); self.emit("auth_lost", {"why": "deactivated"}); return
        changed = 0
        if self.caps["done"] is None:
            try: self.probe()
            except Http: pass
        if self.caps["avatar"] is None:
            try: self.probe_avatar()
            except Http: pass
        if self.caps["paid"] is None:
            try: self.probe_paid()
            except Http: pass
        if self.caps["pext"] is None:
            try: self.probe_pext()
            except Http: pass
        if self.caps["media"] is None:
            try: self.probe_media()
            except Http: pass
        if self.first:
            changed += self._pull(); self._backfill(); self.first = False
        self._push_locked()
        changed += self._pull()
        if time.time() - self.last_recon > 60: changed += self._reconcile_deletes(); self.last_recon = time.time()
        if time.time() - self.last_beat > 60:
            try:
                self._kv("people", json.dumps(self.remote.rest("GET", "profiles", params={"select": self.pcols("id,username,display_name,role,active"), "order": "display_name.asc"})))
            except Http: pass
            try: self.refresh_callers(); changed += 1
            except Http: pass
            try: self.remote.rest("PATCH", "profiles", params={"id": "eq." + self.auth.uid()},
                                  body={"last_seen": now_iso(), "status_text": "Online"}, prefer="return=minimal")
            except Http: pass
            self.last_beat = time.time()
            if self.caps["done"] is False: self.caps["done"] = None          # re-probe in case the migration was run since
            if self.caps["avatar"] is False: self.caps["avatar"] = None
            if self.caps["pext"] is False: self.caps["pext"] = None
            if self.caps["media"] is False: self.caps["media"] = None
            if self.caps["paid"] is False: self.caps["paid"] = None
            try:
                prev = dict(self.profile)
                self.fetch_profile()
                if not self.profile.get("active", True):
                    self.force_sign_out(); self.emit("auth_lost", {"why": "deactivated"}); return
                if prev.get("role") != self.profile.get("role"): self.emit("auth_changed", {})
            except AuthFail:
                pass
        if changed: self.emit("refresh", {})
        self._state("synced" if not self._counts()[1] else "attention")

    # ---- push
    def _push_locked(self):
        with self.push_lock: self._push_all(); self._push_calls(); self._push_avatar(); self._push_ext()

    # ---- manually logged calls (queued locally first, so nothing is lost offline)
    def queue_call(self, rec):
        op = str(uuid.uuid4())
        rec = dict(rec, client_op_id=op)
        with self.lock:
            self.db.execute("INSERT INTO call_queue(op_id,payload,actor,queued_at) VALUES(?,?,?,?)",
                            (op, json.dumps(rec), self.auth.uid(), now_iso())); self.db.commit()
        self._state(self.status["state"]); self.kick()
        return op

    def _push_calls(self):
        with self.lock: rows = self.db.execute("SELECT op_id,payload FROM call_queue WHERE blocked=0 ORDER BY queued_at").fetchall()
        for op, pl in rows:
            try:
                self.remote.rest("POST", "call_log", params={"on_conflict": "client_op_id"}, prefer="resolution=ignore-duplicates,return=minimal", body=json.loads(pl))
                with self.lock: self.db.execute("DELETE FROM call_queue WHERE op_id=?", (op,)); self.db.commit()
            except Http as e:
                transient = e.status in (408, 425, 429, 500, 502, 503, 504) or e.code == "23503"
                with self.lock:
                    self.db.execute("UPDATE call_queue SET attempts=attempts+1,last_error=?,blocked=? WHERE op_id=?", (str(e)[:300], 0 if transient else 1, op)); self.db.commit()

    def _push_all(self):
        with self.lock:
            rows = self.db.execute("SELECT id,tbl,local_id,op,actor,queued_at FROM outbox WHERE blocked=0").fetchall()
        rows.sort(key=lambda r: (SPEC[r[1]]["rank"] if r[3] == "upsert" else 10 - SPEC[r[1]]["rank"], r[0]))
        self._push_new_leads([r for r in rows if r[1] == "leads" and r[3] == "upsert"])
        for r in rows:
            with self.lock:
                if not self.db.execute("SELECT 1 FROM outbox WHERE id=?", (r[0],)).fetchone(): continue
            try: self._push_one(*r)
            except Http as e:
                transient = e.status in (408, 425, 429, 500, 502, 503, 504) or e.code == "23503"   # 23503 = parent not synced yet
                self._fail(r[0], e, block=not transient)

    def _fail(self, oid, e, block):
        with self.lock:
            self.db.execute("UPDATE outbox SET attempts=attempts+1, last_error=?, blocked=? WHERE id=?", (str(e)[:300], 1 if block else 0, oid))
            self.db.commit()

    def _done(self, oid):
        with self.lock:
            self.db.execute("DELETE FROM outbox WHERE id=?", (oid,)); self.db.commit()

    def _local(self, t, lid):
        with self.lock: return self.db.execute(f"SELECT {SPEC[t]['cols']} FROM {t} WHERE id=?", (lid,)).fetchone()

    def _meta(self, t, lid):
        with self.lock:
            return self.db.execute("SELECT remote_id,version,base,aux,op_id FROM sync_meta WHERE tbl=? AND local_id=?", (t, str(lid))).fetchone()

    def _put_meta(self, t, lid, rid, ver, base, aux="", op=""):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO sync_meta(tbl,local_id,remote_id,version,base,aux,op_id) VALUES(?,?,?,?,?,?,?)",
                            (t, str(lid), rid, int(ver), json.dumps(base, default=str), aux, op))
            self.db.commit()

    def _drop_meta(self, t, lid):
        with self.lock:
            self.db.execute("DELETE FROM sync_meta WHERE tbl=? AND local_id=?", (t, str(lid))); self.db.commit()

    def _push_new_leads(self, batch):
        """Fast path for a scrape that added many leads: brand-new, untouched rows go up 100 per request."""
        new, ents = [], []
        for oid, t, lid, op, actor, q in batch:
            if self._meta("leads", lid): continue
            r = self._local("leads", lid)
            if not r: continue
            p = lead_out(r)
            if p["status"] != "none": continue                     # worked leads go one by one so the call is attributed
            if actor: p["added_by"] = actor
            new.append(p); ents.append((oid, lid, p))
        if len(new) < 2: return
        try:
            for i in range(0, len(new), 100):
                got = self.remote.rest("POST", "leads", params={"on_conflict": "id"}, body=new[i:i + 100],
                                       prefer="resolution=ignore-duplicates,return=representation")
                byid = {g["id"]: g for g in got}
                for oid, lid, p in ents[i:i + 100]:
                    g = byid.get(lid)
                    if g:
                        self._put_meta("leads", lid, lid, g["version"], {k: p[k] for k in SPEC["leads"]["keys"]}, p["status"])
                        self._done(oid)
        except Http:
            pass   # e.g. one phone clash rejects the batch; the one-by-one path reports each row precisely

    def _push_one(self, oid, t, lid, op, actor, queued_at):
        meta = self._meta(t, lid)
        if op == "delete": return self._push_delete(oid, t, lid, meta)
        row = self._local(t, lid)
        if row is None: return self._done(oid)
        out = SPEC[t]["out"](row)
        if t == "events" and not out["day"]: return self._block(oid, "Event has no valid date.")
        if t == "deals" and not out["client"]: return self._block(oid, "Deal has no client name.")
        if t == "leads" and not out["name"]: return self._block(oid, "Lead has no name.")
        data = {k: out[k] for k in self.keys(t)}
        if meta is not None and meta[1] == -1: return self._done(oid)     # known duplicate of a shared lead: stays local only
        if meta is None: return self._insert(oid, t, lid, out, data, actor)
        if not meta[0]: return self._insert(oid, t, lid, out, data, actor, op_id=meta[4])   # earlier attempt may have landed
        base = json.loads(meta[2]) if meta[2] else None
        rid = str(lid) if t == "leads" else meta[0]
        body = dict(data)
        if t == "events" and actor and out.get("done") and self.caps.get("done") and not (base or {}).get("done"): body["done_by"] = actor
        if t == "leads" and actor and out["status"] != "none" and meta[3] != out["status"]: body["called_by"] = actor
        got = self.remote.rest("PATCH", t, params={"id": "eq." + rid, "version": "eq." + str(meta[1])}, body=body, prefer="return=representation")
        if got:
            self._put_meta(t, lid, rid, got[0]["version"], data, out["status"] if t == "leads" else "", meta[4])
            self._call_log(t, lid, out, actor, meta)
            self._done(oid)
        else:
            self._resolve(oid, t, lid, rid, out, data, base, queued_at, actor, meta)

    def _insert(self, oid, t, lid, out, data, actor, op_id=None):
        op_id = op_id or str(uuid.uuid4())
        self._put_meta(t, lid, "", 0, None, "", op_id)          # remember the op id BEFORE sending: a lost reply is retried safely
        body = dict(out) if t == "leads" else dict(data, client_op_id=op_id)
        if actor and t == "leads":
            body["added_by"] = actor
            if out["status"] != "none": body["called_by"] = actor
        elif actor and t == "deals": body.update(owner_id=actor, created_by=actor)
        elif actor and t == "events": body["created_by"] = actor
        if t == "events" and actor and out.get("done"): body["done_by"] = actor
        try:
            got = self.remote.rest("POST", t, params={"on_conflict": "id" if t == "leads" else "client_op_id"}, body=body,
                                   prefer="resolution=ignore-duplicates,return=representation")
        except Http as e:
            if e.status == 409 and t == "leads" and e.code == "23505":
                # Another lead in the shared database has this phone number. The local row is KEPT; it is flagged and recorded.
                self._put_meta(t, lid, "", -1, None, "dup", op_id)
                self.conflict(t, lid, "duplicate_phone", {"lead": out.get("name"), "phone": out.get("phone")}, seen=1)
                return self._done(oid)
            raise
        if not got:                                              # the key already existed remotely (our earlier insert landed)
            got = self.remote.rest("GET", t, params={("id" if t == "leads" else "client_op_id"): "eq." + (str(lid) if t == "leads" else op_id), "select": "*"})
            if not got: raise Http(500, "insert returned nothing")
            return self._adopt(oid, t, lid, data, got[0], op_id)
        self._put_meta(t, lid, got[0]["id"], got[0]["version"], data, out["status"] if t == "leads" else "", op_id)
        if t == "events" and actor:
            with self._applying(): self.db.execute("UPDATE events SET created_by=? WHERE id=?", (actor, lid))
        self._call_log(t, lid, out, actor, None)
        self._done(oid)

    def _call_log(self, t, lid, out, actor, meta):
        """When a lead's result changes, record WHO made that call. Idempotent: the same call can never be logged twice."""
        if t != "leads" or not actor or out["status"] not in OUTCOME: return
        if meta is not None and meta[3] == out["status"]: return
        opid = str(uuid.uuid5(NS, f"{lid}|{out['called_at']}|{out['status']}|{actor}"))
        self.remote.rest("POST", "call_log", params={"on_conflict": "client_op_id"}, prefer="resolution=ignore-duplicates,return=minimal",
                         body={"client_op_id": opid, "lead_id": lid, "employee_id": actor, "phone": out["phone"],
                               "started_at": out["called_at"] or now_iso(), "outcome": OUTCOME[out["status"]],
                               "notes": out["notes"], "source": "app"})

    def _adopt(self, oid, t, lid, data, R, op_id):
        remote = {k: R.get(k) for k in self.keys(t)}
        merged, lost = merge3(None, data, remote, False)
        if lost: self.conflict(t, lid, "adopted_remote", {"differences": lost})
        self._apply_local(t, lid, merged)
        self._put_meta(t, lid, R["id"], R["version"], remote, R.get("status", "") if t == "leads" else "", op_id)
        self._done(oid)

    def _resolve(self, oid, t, lid, rid, out, data, base, queued_at, actor, meta):
        cur = self.remote.rest("GET", t, params={"id": "eq." + rid, "select": "*"})
        if not cur:                                              # deleted remotely while we edited: archive our copy, then drop it
            self.conflict(t, lid, "remote_deleted", {"my_copy": data})
            self._delete_local(t, lid); self._drop_meta(t, lid); return self._done(oid)
        R = cur[0]
        remote = {k: R.get(k) for k in data}
        local_newer = (nt(queued_at) or "") > (nt(R.get("updated_at")) or "")
        merged, lost = merge3(base, data, remote, local_newer)
        if lost: self.conflict(t, lid, "edited_on_both", {"fields": lost})
        got = self.remote.rest("PATCH", t, params={"id": "eq." + rid, "version": "eq." + str(R["version"])}, body=merged, prefer="return=representation")
        if not got: raise Http(503, "busy, will retry")
        self._apply_local(t, lid, merged)
        self._put_meta(t, lid, rid, got[0]["version"], merged, meta[3], meta[4])
        self._call_log(t, lid, dict(out, **{k: merged[k] for k in ("status", "called_at") if k in merged}), actor, meta)
        self._done(oid)

    def _block(self, oid, why): self._fail(oid, Exception(why), block=True)

    def _push_delete(self, oid, t, lid, meta):
        if not meta or not meta[0]: return self._done(oid)
        rid = str(lid) if t == "leads" else meta[0]
        got = self.remote.rest("DELETE", t, params={"id": "eq." + rid}, prefer="return=representation")
        if got or not self.remote.rest("GET", t, params={"id": "eq." + rid, "select": "id"}):
            self._drop_meta(t, lid); return self._done(oid)
        # Still there: this account may not delete it. Put it back locally; never silently.
        R = self.remote.rest("GET", t, params={"id": "eq." + rid, "select": "*"})[0]
        self.conflict(t, lid, "delete_not_allowed", {"id": rid})
        self._drop_meta(t, lid)
        nid = self._insert_local(t, R)
        self._put_meta(t, nid, R["id"], R["version"], {k: R.get(k) for k in self.keys(t)}, R.get("status", "") if t == "leads" else "")
        self._done(oid)

    # ---- local writes that must NOT echo back to the outbox
    def _applying(self):
        outer = self

        class Ctx:
            def __enter__(c): outer.lock.acquire(); outer.db.execute("UPDATE sync_kv SET v='1' WHERE k='applying'")
            def __exit__(c, *a):
                try: outer.db.execute("UPDATE sync_kv SET v='0' WHERE k='applying'"); outer.db.commit()
                finally: outer.lock.release()
        return Ctx()

    def _apply_local(self, t, lid, remote_space):
        R = dict(remote_space)
        if t == "leads": R["id"] = lid
        sets = {k: v for k, v in SPEC[t]["inn"](R).items() if k != "id"}
        if t == "leads" and "phone" in sets: sets["pdigits"] = digits10(sets["phone"])
        with self._applying():
            self.db.execute(f"UPDATE {t} SET " + ",".join(f"{k}=?" for k in sets) + " WHERE id=?", (*sets.values(), lid))

    def _delete_local(self, t, lid):
        with self._applying(): self.db.execute(f"DELETE FROM {t} WHERE id=?", (lid,))

    def _insert_local(self, t, R):
        vals = SPEC[t]["inn"](R)
        if t == "leads": vals["pdigits"] = digits10(vals["phone"])
        else: vals["created_at"] = from_iso(R.get("created_at")); vals.pop("id", None)
        with self._applying():
            cur = self.db.execute(f"INSERT INTO {t}({','.join(vals)}) VALUES({','.join('?' * len(vals))})", tuple(vals.values()))
        return str(R["id"]) if t == "leads" else str(cur.lastrowid)

    # ---- pull
    def _pull(self):
        changed = 0
        for t in ("leads", "deals", "events", "notes"):
            cur = self._kv("cur_" + t)
            params = {"select": "*", "order": "updated_at.asc,id.asc"}
            if cur: params["updated_at"] = "gte." + cur
            rows = self.remote.all_pages(t, params)
            for R in rows: changed += self._apply_remote(t, R)
            if rows:
                top = max(nt(x["updated_at"]) for x in rows)
                self._kv("cur_" + t, (datetime.fromisoformat(top) - timedelta(seconds=5)).isoformat())   # small overlap: never miss a row
        return changed

    def _find_local(self, t, R):
        with self.lock:
            if t == "leads":
                x = self.db.execute("SELECT id FROM leads WHERE id=?", (R["id"],)).fetchone()
            else:
                x = self.db.execute("SELECT local_id FROM sync_meta WHERE tbl=? AND remote_id=?", (t, R["id"])).fetchone()
        return x[0] if x else None

    def _apply_remote(self, t, R):
        lid = self._find_local(t, R)
        with self.lock:
            pending = lid is not None and self.db.execute("SELECT 1 FROM outbox WHERE tbl=? AND local_id=?", (t, str(lid))).fetchone()
        if pending: return 0                                  # our edit is queued; the push step merges it
        rs = {k: R.get(k) for k in self.keys(t)}
        aux = R.get("status", "") if t == "leads" else ""
        if lid is None:
            if t != "leads" and self._claim(t, R, rs): return 0
            self._put_meta(t, self._insert_local(t, R), R["id"], R["version"], rs, aux)
            return 1
        meta, have = self._meta(t, lid), SPEC[t]["out"](self._local(t, lid))
        mine = {k: have[k] for k in rs}
        if all(same(mine[k], rs[k], k) for k in rs):
            if not meta or meta[1] != R["version"] or not meta[0]: self._put_meta(t, lid, R["id"], R["version"], rs, aux, meta[4] if meta else "")
            return 0
        if meta is None and t == "leads" and mine["status"] != "none" and rs["status"] == "none":
            # first contact: this PC has real call work the shared copy lacks. Keep it and let the push merge it up.
            self._put_meta(t, lid, R["id"], R["version"], rs, aux)
            with self.lock:
                self.db.execute("INSERT OR REPLACE INTO outbox(tbl,local_id,op,actor,queued_at) VALUES('leads',?,'upsert',(SELECT v FROM sync_kv WHERE k='uid'),?)", (str(lid), now_iso())); self.db.commit()
            return 0
        if meta is None or not meta[0]:
            self.conflict(t, lid, "replaced_by_shared_copy", {"my_copy": mine, "shared": rs})   # remote wins, my copy is archived
        self._apply_local(t, lid, rs)
        self._put_meta(t, lid, R["id"], R["version"], rs, aux, meta[4] if meta else "")
        return 1

    def _claim(self, t, R, rs):
        """A remote deal/event identical to a not-yet-synced local row IS that row (lost-reply case), not a new one."""
        keys = {"deals": ("client", "closed_at", "upfront", "monthly", "months"), "events": ("title", "day", "start_time"), "notes": ("title", "kind", "scope")}[t]
        with self.lock:
            cands = [r[0] for r in self.db.execute(
                f"SELECT id FROM {t} WHERE CAST(id AS TEXT) NOT IN (SELECT local_id FROM sync_meta WHERE tbl=? AND remote_id!='')", (t,))]
        for lid in cands:
            have = SPEC[t]["out"](self._local(t, lid))
            if all(same(have[k], rs.get(k), k) for k in keys):
                self._put_meta(t, lid, R["id"], R["version"], rs)
                if not all(same(have[k], rs.get(k), k) for k in rs):     # local has extra edits: leave/queue them
                    with self.lock:
                        self.db.execute("INSERT OR REPLACE INTO outbox(tbl,local_id,op,actor,queued_at) VALUES(?,?,'upsert','',?)", (t, str(lid), now_iso())); self.db.commit()
                else:
                    with self.lock: self.db.execute("DELETE FROM outbox WHERE tbl=? AND local_id=?", (t, str(lid))); self.db.commit()
                return True
        return False

    def _backfill(self):
        """After the first pull: queue every local row never synced. Actor is blank (unassigned) so nothing is mis-attributed."""
        with self.lock:
            for t in SPEC:
                self.db.execute(f"""INSERT OR IGNORE INTO outbox(tbl,local_id,op,actor,queued_at)
                    SELECT '{t}', CAST(id AS TEXT), 'upsert', '', strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM {t}
                    WHERE CAST(id AS TEXT) NOT IN (SELECT local_id FROM sync_meta WHERE tbl='{t}' AND remote_id!='')""")
            self.db.commit()

    def _reconcile_deletes(self):
        n = 0
        for t in SPEC:
            ids = {r["id"] for r in self.remote.all_pages(t, {"select": "id", "order": "id.asc"})}
            with self.lock:
                mine = self.db.execute("SELECT local_id,remote_id FROM sync_meta WHERE tbl=? AND remote_id!='' AND version>=0", (t,)).fetchall()
                pend = {r[0] for r in self.db.execute("SELECT local_id FROM outbox WHERE tbl=?", (t,))}
            gone = [(l, r) for l, r in mine if r not in ids and l not in pend]
            if len(gone) > 10 and len(gone) > len(mine) / 2:      # mass-delete protection (e.g. wrong project)
                self.conflict(t, "*", "mass_delete_ignored", {"would_remove": len(gone), "of": len(mine)}); continue
            for l, r in gone:
                row = self._local(t, l)
                if row: self.conflict(t, l, "deleted_remotely", {"my_copy": SPEC[t]["out"](row)}); self._delete_local(t, l)
                self._drop_meta(t, l); n += 1
        return n
