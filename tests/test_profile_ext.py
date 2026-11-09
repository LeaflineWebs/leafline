"""Desktop engine: profile extras (title, bio, mood, accent, thought, banner) sync, offline and migration-not-run behaviour."""
import os, sys, tempfile, time, json
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
import leafline_backend as B
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
def until(f, t=15):
    t0 = time.time()
    while time.time() - t0 < t:
        if f(): return True
        time.sleep(.2)
    return False
api = B.Api(); api._ready.set()
check("sign in", api.sign_in("gio", "Gio123")["ok"])
check("sync caught up", until(lambda: api._sync.status["state"] == "synced" and api._sync.caps.get("pext") is True))
G = [p for p in F.t["profiles"] if p["username"] == "gio"][0]
r = api.set_profile_ext({"title": "  Sales   rep ", "bio": "Line one\n  line two  ", "thought": "Be kind.", "mood": "🔥", "accent": "#5C9DFF", "banner": "data:image/jpeg;base64,AAAA"})
check("saved and reported as shared", r["ok"] and r["shared"] and r["ext"]["title"] == "Sales rep" and r["ext"]["bio"] == "Line one\nline two")
check("reached the shared profile", until(lambda: G.get("thought") == "Be kind." and G.get("banner") == "data:image/jpeg;base64,AAAA"))
check("thought has a time stamp", bool(G.get("thought_at")) and G["accent"] == "#5C9DFF" and G["mood"] == "🔥")
check("own profile shows it (me)", api._sync.me()["ext"]["bio"].startswith("Line one") and api.boot()["auth"]["me"]["ext"]["mood"] == "🔥")
ta = G["thought_at"]; api.set_profile_ext({"bio": "changed"}); until(lambda: G.get("bio") == "changed")
check("changing something else keeps the thought time", G["thought_at"] == ta)
api.set_profile_ext({"thought": ""}); until(lambda: not G.get("thought"))
check("clearing the thought clears its time", not G.get("thought") and not G.get("thought_at"))
api.set_profile_ext({"thought": "Again"}); x = api._sync.ext(); x["thought_at"] = "2026-01-01T00:00:00+00:00"; api._sync._kv("pext", json.dumps(x))
api.set_profile_ext({"thought": "Again"})
check("posting the same thought again after 24 hours restarts its clock (it shows again)", api._sync.ext()["thought_at"] > "2026-06")
x = api._sync.ext(); ta2 = x["thought_at"]; api.set_profile_ext({"thought": "Again"})
check("...but within the 24 hours it keeps its time", api._sync.ext()["thought_at"] == ta2)
api.set_profile_ext({"thought": ""}); until(lambda: not G.get("thought"))
check("bad colour refused", not api.set_profile_ext({"accent": "blue"})["ok"])
check("bad banner refused", not api.set_profile_ext({"banner": "javascript:alert(1)"})["ok"])
check("too-long fields are trimmed", len(api.set_profile_ext({"bio": "x" * 999, "thought": "y" * 999, "title": "z" * 99})["ext"]["bio"]) == 280)
t = api.get_team(); me = [p for p in t["people"] if p["name"] == "Gio"][0]
check("team lists the extras for everyone, without the heavy banner", me["ext"]["mood"] == "🔥" and "banner" not in me["ext"] and all("banner" not in p for p in api._sync.people()))
pr = api.get_person(ids["gio"]); check("full card has the banner", pr["ok"] and pr["person"]["banner"] == "data:image/jpeg;base64,AAAA")
print("offline")
F.down = True; api.set_profile_ext({"thought": "Offline thought"}); time.sleep(1)
check("kept on this computer while offline", api._sync.me()["ext"]["thought"] == "Offline thought")
check("sign out is blocked while it is waiting", api.sign_out().get("ok") is False)
F.down = False; check("uploaded after reconnecting", until(lambda: G.get("thought") == "Offline thought", 45))   # the retry after a dropped connection can take a while on a busy machine
check("sign out works once uploaded", until(lambda: api.sign_out().get("ok") is True))
check("sign out wipes the local copy", api._sync.ext()["bio"] == "" and api._sync.ext()["banner"] == "")
print("database update (migration 4) not run yet")
F.pext_cap = False; api._sync.caps["pext"] = None
check("sign in again", api.sign_in("gio", "Gio123")["ok"])
check("probe sees the migration is missing", until(lambda: api._sync.caps.get("pext") is False and api._sync.status["state"] == "synced"))
r = api.set_profile_ext({"bio": "Local only"}); check("saved locally, reported as not shared yet", r["ok"] and r["shared"] is False and api._sync.me()["ext"]["bio"] == "Local only")
t = api.get_team(); check("team still works without the new columns", t["ok"] and len(t["people"]) == 2)
G.pop("thought", None)
F.pext_cap = True; api._sync.caps["pext"] = None; api._sync.last_beat = 0; api._sync.kick()
check("after the migration is run it uploads what was saved", until(lambda: G.get("bio") == "Local only", 25))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
