"""In-memory stand-in for Supabase (auth + REST subset) to test the sync logic offline.
Mimics: password/refresh login, bearer tokens, eq/gte filters, order/limit/offset, on_conflict + ignore-duplicates,
version/updated_at bump on PATCH, unique phone + client_op_id (409/23505), FK on events.lead_id (409/23503),
admin-only delete for leads/deals. It does NOT test real Postgres RLS or the SQL file."""
import json, re, socket, threading, uuid
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


class Fake:
    def __init__(self):
        self.lock = threading.RLock(); self.users = {}; self.tokens = {}; self.refresh = {}
        self.t = {k: [] for k in ("profiles", "leads", "call_log", "deals", "events", "notes", "activity", "settings", "audit_log", "import_batches", "legacy_duplicates", "posts", "post_comments", "post_reactions", "user_settings")}
        self.files = {}; self.media_cap = True; self.posts_cap = True; self.credit_cap = True; self.paid_cap = True
        self.msg_url = None; self._msg_sig = None     # Messages: forwarded to tests/pg/server.mjs (real Postgres) when set
        self.down = False; self.done_cap = True; self.avatar_cap = True; self.pext_cap = True; self.drop_next_write = False; self.expire_tokens = False; self.n = 0
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def add_user(self, name, pw, role="employee"):
        uid = str(uuid.uuid4()); self.users[f"{name}@leaflineweb.com"] = dict(pw=pw, uid=uid)
        self.t["profiles"].append(dict(id=uid, username=name, display_name=name.title(), role=role, active=True,
                                       must_change_password=True, status_text="Offline", last_seen=None))
        return uid

    def now(self):
        self.n += 1
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", f".{self.n % 1000000:06d}+00:00")

    def role(self, uid):
        if uid == "service": return "admin"
        p = next((p for p in self.t["profiles"] if p["id"] == uid), None)
        return p["role"] if p and p["active"] else None

    def _handler(self):
        F = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(s, *a): pass

            def reply(s, code, obj=None, total=None):
                b = json.dumps(obj if obj is not None else []).encode()
                s.send_response(code); s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(b)))
                s.send_header("Access-Control-Allow-Origin", "*"); s.send_header("Access-Control-Expose-Headers", "Content-Range")
                if total is not None: s.send_header("Content-Range", f"0-0/{total}")
                s.end_headers(); s.wfile.write(b)

            def hang_up(s):
                s.close_connection = True
                try: s.connection.shutdown(socket.SHUT_RDWR)
                except OSError: pass

            def go(s, method):
                if F.down: s.hang_up(); return
                u = urlparse(s.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
                n = int(s.headers.get("Content-Length") or 0); raw = s.rfile.read(n) if n else b""
                if F.msg_url and s.msg(method, u, q, raw): return
                if u.path.startswith("/storage/v1/object/"): return s.storage(method, u.path, raw)
                body = json.loads(raw) if raw else None
                with F.lock:
                    if u.path == "/auth/v1/token": return s.auth(q, body)
                    if u.path == "/auth/v1/logout": return s.reply(204)
                    bearer = (s.headers.get("Authorization") or "")[7:]
                    uid = "service" if bearer == "sb_secret_test" else F.tokens.get(bearer)
                    if not uid or F.expire_tokens: return s.reply(401, {"message": "JWT expired"})
                    if u.path == "/auth/v1/user":
                        for v in F.users.values():
                            if v["uid"] == uid: v["pw"] = body["password"]
                        return s.reply(200, {"id": uid})
                    r = s.rest(method, u.path.split("/rest/v1/")[1], q, body, uid)
                    if F.drop_next_write and method in ("POST", "PATCH"):
                        F.drop_next_write = False; s.hang_up(); return
                    return r

            def msg(s, method, u, q, raw):
                """Messages: msg_* functions and the private 'message-files' bucket go to the real-Postgres test server."""
                import urllib.request, urllib.error
                p = u.path; fwd = None; send_uid = True
                if p.startswith("/rest/v1/rpc/msg_") and method == "POST": fwd = ("POST", "/rpc/" + p.rsplit("/", 1)[1], raw)
                elif p.startswith("/storage/v1/object/upload/sign/message-files/"):
                    key = p.split("/message-files/", 1)[1]
                    if method == "POST": fwd = ("POST", "/storage/upload-sign", json.dumps({"path": key}).encode())
                    elif method == "PUT": fwd = ("PUT", "/storage/upload?token=" + q.get("token", ""), raw); send_uid = False
                elif p == "/storage/v1/object/sign/message-files" and method == "POST":
                    b = json.loads(raw or b"{}"); fwd = ("POST", "/storage/sign", json.dumps({"paths": b.get("paths", []), "expiresIn": b.get("expiresIn", 60)}).encode())
                elif p.startswith("/storage/v1/object/sign/message-files/") and method == "GET": fwd = ("GET", "/storage/get?token=" + q.get("token", ""), b""); send_uid = False
                elif p == "/storage/v1/object/message-files" and method == "DELETE": fwd = ("POST", "/storage/remove", raw)
                if not fwd: return False
                h = {"Content-Type": s.headers.get("Content-Type") or "application/json"}
                with F.lock:
                    if send_uid:
                        uid = F.tokens.get((s.headers.get("Authorization") or "")[7:])
                        if not uid or F.expire_tokens: s.reply(401, {"message": "JWT expired"}); return True
                        h["X-Uid"] = uid
                    sig = json.dumps([[(x["id"], x["username"], x["display_name"], x["role"], x["active"]) for x in F.t["profiles"]], F.tokens], sort_keys=True)
                    if sig != F._msg_sig:
                        body = json.dumps({"profiles": [{k: x[k] for k in ("id", "username", "display_name", "role", "active")} for x in F.t["profiles"]], "tokens": F.tokens}).encode()
                        urllib.request.urlopen(urllib.request.Request(F.msg_url + "/sync", data=body, method="POST", headers={"Content-Type": "application/json"}), timeout=30).read()
                        F._msg_sig = sig
                req = urllib.request.Request(F.msg_url + fwd[1], data=fwd[2] if fwd[0] != "GET" else None, method=fwd[0], headers=h)
                try:
                    r = urllib.request.urlopen(req, timeout=60); code, out, ct = r.status, r.read(), r.headers.get("Content-Type")
                except urllib.error.HTTPError as e:
                    code, out, ct = e.code, e.read(), e.headers.get("Content-Type")
                s.send_response(code); s.send_header("Content-Type", ct or "application/json"); s.send_header("Content-Length", str(len(out)))
                s.send_header("Access-Control-Allow-Origin", "*"); s.end_headers(); s.wfile.write(out)
                return True

            def storage(s, method, path, raw):
                if method == "GET" and path.startswith("/storage/v1/object/public/"):
                    f = F.files.get(path.split("/object/public/", 1)[1])
                    if not f: return s.reply(404, {"message": "not found"})
                    s.send_response(200); s.send_header("Content-Type", f[1]); s.send_header("Content-Length", str(len(f[0]))); s.send_header("Access-Control-Allow-Origin", "*"); s.end_headers(); s.wfile.write(f[0]); return
                bearer = (s.headers.get("Authorization") or "")[7:]; uid = F.tokens.get(bearer)
                if not uid: return s.reply(401, {"message": "JWT expired"})
                key = path.split("/storage/v1/object/", 1)[1]
                if not F.media_cap: return s.reply(400, {"message": "Bucket not found"})
                if key.split("/")[1] != uid: return s.reply(403, {"message": "new row violates row-level security policy"})
                if method == "POST":
                    if len(raw) > 8388608: return s.reply(413, {"message": "too large"})
                    F.files[key] = (raw, s.headers.get("Content-Type")); return s.reply(200, {"Key": key})
                if method == "DELETE": F.files.pop(key, None); return s.reply(200, [])
                return s.reply(405, {})

            def auth(s, q, body):
                if q["grant_type"] == "password":
                    u = F.users.get(body["email"])
                    if not u or u["pw"] != body["password"]: return s.reply(400, {"error": "invalid_credentials"})
                    uid = u["uid"]
                else:
                    uid = F.refresh.get(body["refresh_token"])
                    if not uid: return s.reply(400, {"error": "invalid_grant"})
                F.n += 1; at, rt = f"at-{uid}-{F.n}", f"rt-{uid}-{F.n}"; F.tokens[at] = uid; F.refresh[rt] = uid
                F.expire_tokens = False
                s.reply(200, {"access_token": at, "refresh_token": rt, "expires_in": 3600, "user": {"id": uid}})

            def rest(s, method, tbl, q, body, uid):
                if tbl.startswith("rpc/msg_"):           # Messages (migration 8) not run here: answer like Supabase does
                    return s.reply(404, {"code": "PGRST202", "message": "Could not find the function public." + tbl[4:]})
                if tbl.startswith("rpc/note_"):          # note reactions are tested on real Postgres (tests/pg)
                    return s.reply(404, {"code": "PGRST202", "message": "Could not find the function public." + tbl[4:]})
                if tbl in ("rpc/me_settings_get", "rpc/me_settings_set"):   # mirrors migration 9: own row only
                    if not getattr(F, "settings_cap", True): return s.reply(404, {"code": "PGRST202", "message": "Could not find the function public." + tbl[4:]})
                    if not uid: return s.reply(401, {"message": "JWT"})
                    row = next((r for r in F.t["user_settings"] if r["user_id"] == uid), None)
                    if tbl.endswith("_set"):
                        if not isinstance(body.get("p_data"), dict): return s.reply(400, {"code": "P0001", "message": "Settings must be an object"})
                        if not row: row = dict(user_id=uid, data={}); F.t["user_settings"].append(row)
                        row["data"] = {**row["data"], **body["p_data"]}; row["updated_at"] = F.now()
                    return s.reply(200, {"data": row["data"], "updated_at": row["updated_at"]} if row else {})
                if tbl == "rpc/reassign_credit":        # mirrors public.reassign_credit() (migration 6)
                    if not F.credit_cap: return s.reply(404, {"code": "PGRST202", "message": "Could not find the function"})
                    me = uid; to = body["p_to"]; prof = {p["id"]: p for p in F.t["profiles"]}
                    if to not in prof or not prof[to]["active"]: return s.reply(400, {"code": "P0001", "message": "Pick an active teammate"})
                    if body["p_kind"] == "lead": row = next((r for r in F.t["leads"] if r["id"] == body["p_id"]), None); key = "called_by"; what = row and row["name"]
                    else: row = next((r for r in F.t["deals"] if r["id"] == body["p_id"]), None); key = "owner_id"; what = row and row["client"]
                    if not row: return s.reply(400, {"code": "P0001", "message": "not found"})
                    cur = row.get(key)
                    if not (F.role(me) == "admin" or cur is None or cur == me or to == me): return s.reply(400, {"code": "P0001", "message": "Only the person who has it, the person it is for, or an admin can move it"})
                    row[key] = to; row["version"] = row.get("version", 0) + 1; row["updated_at"] = F.now()
                    if body["p_kind"] == "lead":
                        for c in F.t["call_log"]:
                            if c.get("lead_id") == body["p_id"] and c["outcome"] in ("meeting_booked", "sale_completed"): c["credited_to"] = to
                    F.t["activity"].append(dict(id=len(F.t["activity"]) + 1, employee_id=me, kind="credit", summary=f"{prof[me]['display_name']} " + ("took credit for " + what if to == me else f"gave {what} to {prof[to]['display_name']}"), ref_table="leads", ref_id=body["p_id"], created_at=F.now()))
                    return s.reply(200, {"ok": True})
                if tbl == "rpc/daily_stats":            # mirrors public.daily_stats() in the SQL file
                    g = {}
                    for c in F.t["call_log"]:
                        d = datetime.fromisoformat(c["started_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Toronto")).date().isoformat()
                        if not (body["p_from"] <= d <= body["p_to"]): continue
                        r = g.setdefault((d, c["employee_id"]), dict(day=d, employee_id=c["employee_id"], calls=0, connections=0, leads=set(), meetings=0, sales=0))
                        r["calls"] += 1; r["leads"].add(c.get("lead_id"))
                        r["connections"] += c["outcome"] in ("interested", "not_interested", "follow_up", "meeting_booked", "sale_completed")
                        cr = c.get("credited_to") or c["employee_id"]
                        if c["outcome"] in ("meeting_booked", "sale_completed"):
                            r2 = g.setdefault((d, cr), dict(day=d, employee_id=cr, calls=0, connections=0, leads=set(), meetings=0, sales=0))
                            r2["meetings"] += c["outcome"] == "meeting_booked"; r2["sales"] += c["outcome"] == "sale_completed"
                    return s.reply(200, [dict({k: v for k, v in r.items() if k != "leads"}, prospects=len(r["leads"])) for r in g.values()])
                rows = F.t[tbl]
                if tbl == "events" and not F.done_cap:       # the optional 2nd migration has not been run
                    if "done" in q.get("select", "") or any(k in ("done", "done_at") for k in q) or any(k in ("done", "done_at", "done_by") for it in ((body if isinstance(body, list) else [body]) if body else []) for k in it):
                        return s.reply(400, {"code": "42703", "message": "column events.done does not exist"})
                cols = set(q.get("select", "").split(","))      # exact column names, like PostgREST
                if tbl == "deals" and not F.paid_cap and ("confirmed" in cols or any("confirmed" in it for it in ((body if isinstance(body, list) else [body]) if isinstance(body, (dict, list)) else []))):
                    return s.reply(400, {"code": "42703", "message": "column deals.confirmed does not exist"})
                if tbl == "profiles" and not F.avatar_cap and ("avatar" in cols or (isinstance(body, dict) and "avatar" in body)):
                    return s.reply(400, {"code": "42703", "message": "column profiles.avatar does not exist"})
                PX = ("bio", "thought", "thought_at", "title", "mood", "accent", "banner")
                if tbl == "profiles" and not F.pext_cap and (any(c in cols for c in PX) or (isinstance(body, dict) and any(c in body for c in PX))):
                    return s.reply(400, {"code": "42703", "message": "column profiles.bio does not exist"})
                if tbl.startswith("post") and not F.posts_cap: return s.reply(404, {"code": "PGRST205", "message": "Could not find the table 'public.posts' in the schema cache"})
                MX = ("avatar_url", "banner_url", "banner_pos")
                if tbl == "profiles" and not F.media_cap and (any(c in cols for c in MX) or (isinstance(body, dict) and any(c in body for c in MX))):
                    return s.reply(400, {"code": "42703", "message": "column profiles.avatar_url does not exist"})
                if tbl == "posts" and method == "PATCH":      # mirrors guard_post(): author is kept, edits are stamped
                    body = {k: v for k, v in body.items() if k not in ("id", "author_id", "created_at")}
                    if any(k in body for k in ("title", "body", "kind")): body.update(edited_by=uid, edited_at=F.now())
                if tbl in ("posts", "post_comments") and method == "POST" and any(it.get("author_id") != uid for it in (body if isinstance(body, list) else [body])): return s.reply(403, {"code": "42501"})
                if tbl == "post_reactions" and method == "DELETE" and q.get("user_id") != "eq." + uid: return s.reply(403, {"code": "42501"})
                if tbl == "notes" and F.role(uid) != "service":
                    rows = [r for r in rows if r.get("scope") == "shared" or r.get("owner_id") == uid] if method != "POST" else rows
                if tbl == "profiles" and method == "PATCH" and F.role(uid) != "admin" and q.get("id") != "eq." + uid: return s.reply(403, {"code": "42501"})
                if tbl == "settings" and method == "POST" and F.role(uid) != "admin": return s.reply(403, {"code": "42501"})
                def cmp(r, k, op, val):
                    v = r.get(k)
                    if op == "eq": return str(v).lower() == val.lower() if isinstance(v, bool) else str(v) == val
                    if op == "is": return v is None if val == "null" else str(v) == val
                    if op == "gte": return str(v) >= val
                    if op == "lt": return str(v) < val
                    if op == "in": return str(v) in val.strip("()").split(",")
                    return True
                def match(r):
                    for k, v in q.items():
                        if k in ("select", "order", "limit", "offset", "on_conflict"): continue
                        if k == "and":
                            for part in v.strip("()").split(","):
                                kk, op, val = part.split(".", 2)
                                if not cmp(r, kk, op, val): return False
                            continue
                        op, _, val = v.partition(".")
                        if not cmp(r, k, op, val): return False
                    return True
                prefer = s.headers.get("Prefer", "")
                if method == "GET":
                    out = [r for r in rows if match(r)]
                    for key in reversed(q.get("order", "").split(",")):
                        if key: out.sort(key=lambda r: str(r.get(key.split(".")[0])), reverse=key.endswith(".desc"))
                    off, lim = int(q.get("offset", 0)), int(q.get("limit", 100000))
                    return s.reply(200, [dict(r) for r in out[off:off + lim]], total=len(out))
                if method == "POST":
                    made = []
                    for it in (body if isinstance(body, list) else [body]):
                        it = dict(it)
                        if tbl not in ("leads", "post_reactions"): it.setdefault("id", str(uuid.uuid4()))
                        if tbl == "post_reactions" and any(r["post_id"] == it["post_id"] and r["user_id"] == it["user_id"] and r["emoji"] == it["emoji"] for r in rows): return s.reply(409, {"code": "23505"})
                        if tbl == "posts": it.setdefault("pinned", False); it.setdefault("kind", "announcement"); it.setdefault("edited_by", None); it.setdefault("edited_at", None)
                        key = q.get("on_conflict")
                        if key and it.get(key) is not None and any(r.get(key) == it[key] for r in rows + made):
                            if "merge-duplicates" in prefer:
                                for r in rows:
                                    if r.get(key) == it[key]: r.update(it)
                                continue
                            if "ignore-duplicates" in prefer: continue
                            return s.reply(409, {"code": "23505"})
                        if tbl == "leads":
                            k = re.sub(r"\D", "", it.get("phone", ""))[-10:]
                            if k and any(re.sub(r"\D", "", r["phone"])[-10:] == k for r in rows + made):
                                return s.reply(409, {"code": "23505", "message": "leads_phone_key_uq"})
                        if tbl == "events" and it.get("lead_id") and not any(r["id"] == it["lead_id"] for r in F.t["leads"]):
                            return s.reply(409, {"code": "23503"})
                        if tbl == "call_log" and it.get("employee_id") != uid and F.role(uid) != "admin":
                            return s.reply(403, {"code": "42501"})
                        if tbl == "notes": it.setdefault("owner_id", uid)
                        it.update(version=1, updated_at=F.now(), created_at=F.now())
                        if tbl == "leads": it["phone_key"] = re.sub(r"\D", "", it.get("phone", ""))[-10:]
                        made.append(it)
                    rows.extend(made)
                    return s.reply(201, made if "representation" in prefer else [])
                if method == "PATCH":
                    out = []
                    for r in rows:
                        if match(r): r.update(body); r["version"] = r.get("version", 0) + 1; r["updated_at"] = F.now(); out.append(dict(r))
                    return s.reply(200, out if "representation" in prefer else [])
                if method == "DELETE":
                    ok = F.role(uid) == "admin" or tbl in ("events", "notes", "posts", "post_comments", "post_reactions")
                    gone = [r for r in rows if match(r)] if ok else []
                    if tbl == "notes" and F.role(uid) != "admin": gone = [r for r in gone if r.get("owner_id") == uid]
                    for r in gone: F.t[tbl].remove(r)
                    if tbl == "posts":
                        for t2 in ("post_comments", "post_reactions"): F.t[t2][:] = [r for r in F.t[t2] if r["post_id"] not in {g["id"] for g in gone}]
                    return s.reply(200, [dict(r) for r in gone] if "representation" in prefer else [])

            def do_OPTIONS(s):
                s.send_response(204); s.send_header("Access-Control-Allow-Origin", "*"); s.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,PUT,DELETE,OPTIONS")
                s.send_header("Access-Control-Allow-Headers", "authorization,apikey,content-type,prefer,x-client-info,x-upsert,cache-control"); s.send_header("Content-Length", "0"); s.end_headers()
            def do_GET(s): s.go("GET")
            def do_POST(s): s.go("POST")
            def do_PATCH(s): s.go("PATCH")
            def do_PUT(s): s.go("PUT")
            def do_DELETE(s): s.go("DELETE")
        return H
