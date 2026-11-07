"""New features: notes + scripts, script dock, call log, admin tools, task done, calendar views. Backend (two PCs) + real browser."""
import os, sys, tempfile, threading, time, json, re
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "james", "jaylen")}
for p in F.t["profiles"]: p["must_change_password"] = False
import leafline_backend as B, leafline_sync as L
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
def pc(name):
    """A separate 'computer': its own home folder, database and session."""
    home = tempfile.mkdtemp(); os.environ["HOME"] = home; os.environ["USERPROFILE"] = home
    import importlib; B.DATA = home; B.PROFILE = os.path.join(home, "profile.json"); B.DB = os.path.join(home, "leads.db")
    a = B.Api(); r = a.sign_in(name, name.title() + "123"); assert r["ok"], r
    return a
def settle(*apis, secs=12):
    t0 = time.time()
    while time.time() - t0 < secs:
        for a in apis: a._sync.kick()
        time.sleep(.5)
        if all(a._sync._counts()[0] == 0 for a in apis) and time.time() - t0 > 2.5: break
    time.sleep(1.5)
    for a in apis: a._sync.kick()
    time.sleep(1.5)

print("1. sanitiser")
dirty = '<p style="color:red;background:url(x)" onclick="x()">Hi <b>there</b><script>alert(1)</script><a href="javascript:x">a</a><a href="https://ok.com">l</a><img src=x onerror=y><iframe src=z></iframe></p>'
c = B.sanitize_html(dirty)
check("scripts, handlers, javascript: links, images, iframes removed", not re.search(r"script|onclick|javascript|<img|iframe|onerror|url\(", c))
check("bold, colour and safe links kept", "<b>there</b>" in c and "color:red" in c and 'href="https://ok.com"' in c)

print("2. notes sync between computers")
g = pc("gio"); j = pc("james")
r = g.save_note(dict(kind="script", scope="personal", title="My opener", body="<p>Hi, <b>Leafline</b> here</p><script>x</script>"))
check("script saved and cleaned", r["ok"] and "<script" not in r["body"] and "<b>Leafline</b>" in r["body"])
g.save_note(dict(kind="note", scope="shared", title="Team pricing", body="Starter $500"))
g.save_note(dict(kind="note", scope="personal", title="Gio private", body="secret"))
settle(g, j)
tj = [n["title"] for n in j.get_notes()]
check("shared note reaches James", "Team pricing" in tj)
check("Gio's personal notes & scripts stay private", "Gio private" not in tj and "My opener" not in tj)
check("shared database holds all three", {n["title"] for n in F.t["notes"]} == {"My opener", "Team pricing", "Gio private"})
sh = next(n for n in j.get_notes() if n["title"] == "Team pricing")
check("shared note shows its owner and 'mine' is false for James", sh["owner"] == "Gio" and not sh["mine"])
j.save_note(dict(id=sh["id"], kind="note", scope="shared", title="Team pricing", body="Starter $500\nPro $900"))
settle(g, j)
check("James's edit of a shared note reaches Gio", "Pro $900" in next(n for n in g.get_notes() if n["title"] == "Team pricing")["body"])
rj = j.save_note(dict(id=sh["id"], kind="note", scope="personal", title="Team pricing", body="x"))
check("only the owner can make a shared note private", j.get_notes() and next(n for n in j.get_notes() if n["id"] == sh["id"])["scope"] == "shared")
d = j.delete_note(sh["id"]); settle(g, j); g._sync.last_recon = 0; settle(g)
check("an admin may delete a shared note; it disappears for Gio", d["ok"] and "Team pricing" not in [n["title"] for n in g.get_notes()])
# offline editing is queued, nothing lost
sc = next(n for n in g.get_notes() if n["title"] == "My opener")
F.down = True
g.save_note(dict(id=sc["id"], kind="script", scope="personal", title="My opener", body="<p>edited offline</p>")); time.sleep(1.5)
check("offline edit is kept and counted as waiting", next(n for n in g.get_notes() if n["id"] == sc["id"])["unsynced"])
F.down = False; settle(g)
check("offline edit uploads when the connection returns", any("edited offline" in n["body"] for n in F.t["notes"]))
# two PCs same person, offline conflict
big = "<p>" + "long " * 3000 + "</p>"
check("very long script saves", g.save_note(dict(kind="script", title="Long", body=big))["ok"])
check("too-long text refused politely", not g.save_note(dict(kind="note", title="Huge", body="x" * 700000))["ok"])

print("3. call log")
lead = "L1"
with g._lock: g._db.execute("INSERT INTO leads(id,name,phone,pdigits,btype,search,status,added_at) VALUES(?,?,?,?,?,?,?,?)", (lead, "Maple Roofing", "+1-519-555-0101", "5195550101", "Roofing", "Roofing | KW", "none", "2026-11-06 09:00"))
g._sync.kick(); settle(g)
check("rejects a call without an outcome", not g.log_call(dict(lead_id=lead))["ok"])
check("rejects a call with no business or phone", not g.log_call(dict(outcome="no_answer"))["ok"])
for o in ("voicemail", "interested", "follow_up"): assert g.log_call(dict(lead_id=lead, outcome=o, notes="n-" + o))["ok"]
F.down = True; time.sleep(.5); ok_q = g.log_call(dict(phone="(226) 555-0199", outcome="no_answer"))["ok"]; pend = g.get_calls({})
check("logged offline: queued and shown as waiting", ok_q and pend["stale"] and any(x["pending"] for x in pend["rows"]))
F.down = False; settle(g)
rows = g.get_calls({})["rows"]
check("all four calls reached the shared log with Gio as the caller", len([x for x in F.t["call_log"] if x["employee_id"] == ids["gio"]]) == 4)
check("each row names the caller and business", rows and all(x["who"] == "Gio" for x in rows) and any(x["business"] == "Maple Roofing" for x in rows))
check("filter by outcome", [x["outcome"] for x in g.get_calls({"outcome": "voicemail"})["rows"]] == ["voicemail"])
check("filter by prospect name", len(g.get_calls({"q": "maple"})["rows"]) == 3)
check("filter by phone digits", len(g.get_calls({"q": "2265550199"})["rows"]) == 1)
check("filter by employee", len(g.get_calls({"employee": ids["james"]})["rows"]) == 0 and len(g.get_calls({"employee": ids["gio"]})["rows"]) == 4)
F.t["call_log"].append(dict(id="old", employee_id=None, lead_id=lead, phone="", outcome="interested", started_at="2026-10-01T15:00:00+00:00", source="legacy_status", version=1))
check("older unassigned records are labelled, not hidden", any(x["legacy"] for x in g.get_calls({})["rows"]) and len(g.get_calls({"employee": "none"})["rows"]) == 1)
check("date range filter", len(g.get_calls({"from": "2026-10-01", "to": "2026-10-02"})["rows"]) == 1)
check("James sees Gio's calls (shared)", len(j.get_calls({"employee": ids["gio"]})["rows"]) == 4)

print("4. admin tools")
check("non-admin refused: people", not g.admin_people()["ok"])
check("non-admin refused: targets", not g.admin_targets(dict(calls=1))["ok"])
check("non-admin refused: deactivate", not g.admin_update(ids["jaylen"], active=False)["ok"])
check("non-admin refused: export", not g.admin_export("x")["ok"])
ap = j.admin_people()
check("admin sees every person", ap["ok"] and len(ap["people"]) == 3)
check("admin sets targets", j.admin_targets(dict(calls=80, connections=15, meetings=2, sales=1))["ok"] and next(s for s in F.t["settings"] if s["key"] == "daily_targets")["value"]["calls"] == 80)
check("targets feed the team dashboard", j.get_team()["targets"]["calls"] == 80)
check("admin cannot deactivate self", not j.admin_update(ids["james"], active=False)["ok"])
check("admin changes a role", j.admin_update(ids["jaylen"], role="admin")["ok"] and next(p for p in F.t["profiles"] if p["id"] == ids["jaylen"])["role"] == "admin")
j.admin_update(ids["jaylen"], role="employee")
out = os.path.join(tempfile.mkdtemp(), "co.csv"); ex = j.admin_export(out)
check("export writes one file per table", ex["ok"] and len(ex["files"]) == 5 and all(os.path.exists(os.path.join(ex["folder"], f["file"])) for f in ex["files"]))
cs = open(os.path.join(ex["folder"], "co_calls.csv"), encoding="utf-8-sig").read()
check("exported calls contain the logged calls", "voicemail" in cs and "interested" in cs)
# deactivation signs the person out
ev = []; jay = pc("jaylen"); jay._sync.emit = lambda e, d=None: ev.append(e)
j.admin_update(ids["jaylen"], active=False)
jay._sync.last_beat = 0; t0 = time.time()
while time.time() - t0 < 12 and jay._sync.auth.s: jay._sync.kick(); time.sleep(.5)
check("a deactivated person is signed out of their app", jay._sync.auth.s is None and "auth_lost" in ev)

print("5. tasks (events marked done)")
e = g.save_event(dict(title="Call back Maple", date="2026-11-06", time="10:00", repeat="none", icon="check", color="#3DDC84")); settle(g)
eid = g._db.execute("SELECT id FROM events WHERE title='Call back Maple'").fetchone()[0]
g.set_event_done(eid, True); settle(g)
re_ = next(x for x in F.t["events"] if x["title"] == "Call back Maple")
check("done state syncs with who finished it", re_.get("done") is True or re_.get("done") == 1)
check("done_by is the person who ticked it", re_.get("done_by") == ids["gio"])
tm = g.get_team(); check("team card counts tasks done", tm["tasks_enabled"] and next(p for p in tm["people"] if p["name"] == "Gio")["today"]["tasks"] == 1)
g.set_event_done(eid, False); settle(g)
check("un-ticking syncs", not next(x for x in F.t["events"] if x["title"] == "Call back Maple").get("done"))
print("   -- before the optional migration is run")
F.done_cap = False; g._sync.caps["done"] = None; g.save_event(dict(id=eid, title="Call back Maple", date="2026-11-06", time="10:00", repeat="none")); g.set_event_done(eid, True); settle(g, secs=8)
check("without the migration nothing breaks (sync stays healthy)", g._sync.status["state"] in ("synced", "syncing") and g._sync._counts()[1] == 0)
check("tasks are simply not counted yet", not g.get_team().get("tasks_enabled"))
F.done_cap = True; g._sync.caps["done"] = None; settle(g, secs=8)
check("once the migration exists the done state uploads", next(x for x in F.t["events"] if x["title"] == "Call back Maple").get("done") in (True, 1))

print("5b. profile pictures")
import base64
img = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8fakejpeg" * 20).decode()
check("bad picture refused", not g.set_avatar("javascript:alert(1)")["ok"] and not g.set_avatar("data:text/html;base64,AAAA")["ok"])
check("oversized picture refused", not g.set_avatar("data:image/png;base64," + "A" * 70000)["ok"])
r = g.set_avatar(img); settle(g)
check("picture saved and shared", r["ok"] and r["shared"] and next(p for p in F.t["profiles"] if p["id"] == ids["gio"])["avatar"] == img)
check("own picture available to the app", g._sync.me()["avatar"] == img)
tm = j.get_team(); check("James sees Gio's picture on the team page data", next(p for p in tm["people"] if p["name"] == "Gio")["avatar"] == img and next(p for p in tm["people"] if p["name"] == "James")["avatar"] == "")
check("a fresh sign-in on another PC gets the picture", pc("gio")._sync.me()["avatar"] == img)
F.down = True; g.set_avatar(""); time.sleep(.5); F.down = False; settle(g)
check("removing a picture while offline uploads later", next(p for p in F.t["profiles"] if p["id"] == ids["gio"]).get("avatar") in (None, ""))
F.avatar_cap = False; g._sync.caps["avatar"] = None; g.set_avatar(img); settle(g, secs=6)
check("without the database update nothing breaks and Team still loads", g._sync.status["state"] in ("synced", "syncing") and g.get_team()["ok"] and g._sync.me()["avatar"] == img)
F.avatar_cap = True; g._sync.caps["avatar"] = None; settle(g, secs=8)
check("picture uploads once the update exists", next(p for p in F.t["profiles"] if p["id"] == ids["gio"]).get("avatar") == img)

print("6. preferences")
g.set_pref("dockW", 420); check("saved on this computer", g.get_prefs()["dockW"] == 420)

print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
