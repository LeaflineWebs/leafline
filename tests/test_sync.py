import os, sys, tempfile, threading, sqlite3, json
os.environ["NO_PROXY"] = "127.0.0.1"; os.environ["no_proxy"] = "127.0.0.1"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
import leafline_backend as B, leafline_sync as S
from fake_supabase import Fake

TODAY = __import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('America/Toronto')).date().isoformat()
F = Fake(); S.SUPABASE_URL = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n in ("james", "omar", "akbar") else "employee") for n in ("gio", "james", "akbar", "omar", "jaylen", "tim")}
events = []

def pc(name):
    d = tempfile.mkdtemp(); db = B.open_db(os.path.join(d, "leads_v2.db"))
    s = S.Sync(db, threading.RLock(), lambda e, x=None: events.append((name, e)), d); s.name = name; s.d = d; return s

def login(s, pw=None):
    s.sign_in(s.name, pw or s.name.title() + "123")

def cyc(s, n=3):
    for _ in range(n): s._cycle()

def add(s, id, name, phone, status="none"):
    with s.lock:
        s.db.execute("INSERT INTO leads(id,name,phone,pdigits,btype,search,status,added_at,called_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (id, name, phone, S.digits10(phone), "Roofing", "Roofing | Kitchener", status, "2026-11-06 10:00", "2026-11-06 10:05" if status != "none" else None)); s.db.commit()

def sql(s, q, *a):
    with s.lock: r = s.db.execute(q, a).fetchall(); s.db.commit(); return r

def outbox(s): return sql(s, "SELECT COUNT(*) FROM outbox")[0][0]
def rl(): return {r["id"]: r for r in F.t["leads"]}
ok = fail = 0
def check(label, cond):
    global ok, fail
    if cond: ok += 1; print("  PASS", label)
    else: fail += 1; print("  FAIL", label)

gio, james, akbar, jay = pc("gio"), pc("james"), pc("akbar"), pc("jaylen")
print("1. login / basics")
try: gio.auth.login("gio", "wrong"); check("wrong password rejected", False)
except S.AuthFail: check("wrong password rejected", True)
login(gio); check("gio profile loads", gio.me()["display_name"] == "Gio" and gio.me()["must_change_password"])
gio.change_password("NewGio!9"); check("password change clears the flag", gio.profile["must_change_password"] is False and F.users["gio@leaflineweb.com"]["pw"] == "NewGio!9")
check("session file stored", os.path.exists(os.path.join(gio.d, "session.json")))
g2 = S.Sync(gio.db, gio.lock, lambda *a: None, gio.d); check("saved session restores silently", g2.restore()["username"] == "gio")

print("2. sync between two PCs")
for i in range(1, 4): add(gio, f"p{i}", f"Biz {i}", f"+1-519-555-010{i}")
cyc(gio); check("3 leads reached shared db (batch)", len(F.t["leads"]) == 3 and outbox(gio) == 0)
check("added_by is gio", all(r["added_by"] == ids["gio"] for r in F.t["leads"]))
login(james); cyc(james); check("james sees all 3", len(sql(james, "SELECT * FROM leads")) == 3)
check("no echo: james outbox empty after pull", outbox(james) == 0)
sql(gio, "UPDATE leads SET status='orange', called_at='2026-11-06 11:00' WHERE id='p1'"); cyc(gio)
check("remote status updated", rl()["p1"]["status"] == "orange" and rl()["p1"]["version"] == 2)
check("call_log row attributed to gio", [c["employee_id"] for c in F.t["call_log"]] == [ids["gio"]] and F.t["call_log"][0]["outcome"] == "no_answer")
cyc(james); check("james sees status change automatically", sql(james, "SELECT status FROM leads WHERE id='p1'")[0][0] == "orange")
cyc(gio); check("no duplicate call_log on later cycles", len(F.t["call_log"]) == 1)

print("3. conflicts")
sql(gio, "UPDATE leads SET notes='gio note' WHERE id='p2'"); sql(james, "UPDATE leads SET owner='Sam Smith' WHERE id='p2'")
cyc(gio); cyc(james); cyc(gio)
r = rl()["p2"]; check("different fields both kept (merged)", r["notes"] == "gio note" and r["owner_name"] == "Sam Smith")
check("both PCs converge", sql(gio, "SELECT notes,owner FROM leads WHERE id='p2'") == sql(james, "SELECT notes,owner FROM leads WHERE id='p2'") == [("gio note", "Sam Smith")])
sql(gio, "UPDATE leads SET notes='from gio' WHERE id='p3'"); sql(james, "UPDATE leads SET notes='from james' WHERE id='p3'")
cyc(gio); cyc(james); cyc(gio)
cf = [json.loads(c[0]) for c in sql(james, "SELECT detail FROM sync_conflicts WHERE kind='edited_on_both'")]
check("same-field clash recorded with both values", any(f["field"] == "notes" and {f["mine"], f["theirs"]} == {"from gio", "from james"} for c in cf for f in c["fields"]))
check("PCs converge after clash", sql(gio, "SELECT notes FROM leads WHERE id='p3'") == sql(james, "SELECT notes FROM leads WHERE id='p3'"))

print("4. offline + retry")
sql(james, "UPDATE leads SET notes='offline edit' WHERE id='p1'"); add(james, "p9", "Offline Biz", "+1-519-555-0199")
F.down = True
try: james._cycle(); check("offline detected", False)
except S.Offline: check("offline detected", True)
check("changes wait in outbox, not lost", outbox(james) >= 2)
F.down = False; cyc(james); check("outbox drains after reconnect", outbox(james) == 0 and rl()["p1"]["notes"] == "offline edit" and "p9" in rl())

print("5. lost reply on insert (no duplicates)")
with james.lock:
    james.db.execute("INSERT INTO deals(client,upfront,monthly,months,closed_at,first_bill,notes,created_at) VALUES('Maple Roofing',500,35,3,'"+TODAY+"','"+TODAY+"','','"+TODAY+" 12:00')"); james.db.commit()
F.drop_next_write = True
try: james._cycle()
except Exception: pass
check("write landed but reply lost", len(F.t["deals"]) == 1)
cyc(james); check("retry did NOT create a 2nd deal", len(F.t["deals"]) == 1 and outbox(james) == 0)
cyc(gio); check("gio receives the deal", sql(gio, "SELECT client FROM deals") == [("Maple Roofing",)])
check("deal owner is james", F.t["deals"][0]["owner_id"] == ids["james"])

print("6. duplicate phone from another PC")
add(gio, "dupX", "Same Phone Biz", "+1 (519) 555-0101"); cyc(gio)
check("shared db has no duplicate phone", sum(1 for r in F.t["leads"] if r["phone_key"] == "5195550101") == 1)
check("local row kept, conflict recorded", sql(gio, "SELECT COUNT(*) FROM leads WHERE id='dupX'")[0][0] == 1 and sql(gio, "SELECT COUNT(*) FROM sync_conflicts WHERE kind='duplicate_phone'")[0][0] == 1 and outbox(gio) == 0)

print("7. calendar events + delete rights")
with gio.lock: gio.db.execute("INSERT INTO events(title,day,start_time,color,icon,repeat_kind,until,notes,lead_id,created_at) VALUES('Call back Biz 1','2026-11-09','10:00','#34D27B','phone','none','','', 'p1','2026-11-06 12:00')"); gio.db.commit()
cyc(gio); cyc(james); check("event shared", sql(james, "SELECT title,lead_id FROM events") == [("Call back Biz 1", "p1")])
sql(james, "UPDATE events SET title='Call back (moved)', day='2026-11-10'"); cyc(james); cyc(gio); check("event edit reaches gio", sql(gio, "SELECT title,day FROM events") == [("Call back (moved)", "2026-11-10")])
login(jay); cyc(jay); sql(jay, "DELETE FROM leads WHERE id='p2'"); cyc(jay)
check("non-admin delete refused, lead restored locally", "p2" in rl() and sql(jay, "SELECT COUNT(*) FROM leads WHERE id='p2'")[0][0] == 1 and sql(jay, "SELECT COUNT(*) FROM sync_conflicts WHERE kind='delete_not_allowed'")[0][0] == 1)
sql(james, "DELETE FROM leads WHERE id='p3'"); cyc(james); gio.last_recon = 0; cyc(gio)
check("admin delete propagates", "p3" not in rl() and sql(gio, "SELECT COUNT(*) FROM leads WHERE id='p3'")[0][0] == 0)

print("8. sessions")
F.expire_tokens = True; sql(gio, "UPDATE leads SET notes='after expiry' WHERE id='p1'"); cyc(gio); check("expired token refreshed transparently", rl()["p1"]["notes"] == "after expiry")
add(akbar, "ak1", "Akbar Lead", "+1-226-555-0111"); login(akbar); akbar.first = False
sql(akbar, "UPDATE leads SET status='red', called_at='2026-11-06 13:00' WHERE id='ak1'")
F.down = True
res = akbar.sign_out(); check("sign-out refused while changes are unsynced", res["ok"] is False and res["pending"] >= 1 and akbar.auth.s is not None)
try: akbar.sign_in("jaylen", "Jaylen123"); check("other employee blocked while akbar's changes are unsynced", False)
except (S.AuthFail, S.Offline) as e: check("other employee blocked while akbar's changes are unsynced", True)
F.down = False; cyc(akbar); res = akbar.sign_out(); check("sign-out works once synced; session cleared", res["ok"] is True and akbar.auth.s is None and not os.path.exists(os.path.join(akbar.d, "session.json")))
check("akbar's call attributed to akbar", any(c["employee_id"] == ids["akbar"] and c["outcome"] == "not_interested" for c in F.t["call_log"]))
F.t["profiles"][4]["active"] = False
try: pc("jaylen").sign_in("jaylen", "Jaylen123"); check("deactivated account cannot sign in", False)
except S.AuthFail: check("deactivated account cannot sign in", True)

print("9. calendar assignment + creator")
james2 = pc("james"); login(james2); cyc(james2)
with james2.lock:
    james2.db.execute("INSERT INTO events(title,day,start_time,color,icon,repeat_kind,until,notes,lead_id,assigned_to,created_at,created_by) VALUES('Team demo','2026-11-12','14:00','#3DDC84','star','none','','','',?,'2026-11-06 12:00',?)", (ids["jaylen"], ids["james"])); james2.db.commit()
cyc(james2); ev = next(e for e in F.t["events"] if e["title"] == "Team demo")
check("assigned_to and created_by reach the shared db", ev["assigned_to"] == ids["jaylen"] and ev["created_by"] == ids["james"])
F.t["profiles"][4]["active"] = True; jay2 = pc("jaylen"); jay2.sign_in("jaylen", "Jaylen123"); cyc(jay2)
row = sql(jay2, "SELECT title,assigned_to,created_by FROM events WHERE title='Team demo'")
check("jaylen sees who created it and that it is assigned to him", row == [("Team demo", ids["jaylen"], ids["james"])])
sql(jay2, "UPDATE events SET assigned_to=? WHERE title='Team demo'", ids["tim"]); cyc(jay2)
check("re-assigning syncs without wiping the creator", ev["assigned_to"] == ids["tim"] and ev["created_by"] == ids["james"])
cyc(james2); check("james sees the new assignee", sql(james2, "SELECT assigned_to,created_by FROM events WHERE title='Team demo'") == [(ids["tim"], ids["james"])])

print("10. team dashboard numbers")
from datetime import datetime, timezone
nowi = datetime.now(timezone.utc).isoformat()
F.t["call_log"].clear()
def call(emp, outcome, lead="p1", src="app"): F.t["call_log"].append(dict(id=str(len(F.t["call_log"])), employee_id=ids[emp], lead_id=lead, outcome=outcome, started_at=nowi, source=src, version=1))
for o in ("no_answer", "voicemail", "interested", "meeting_booked"): call("gio", o, "p1" if o != "interested" else "p2")
call("james", "sale_completed"); call("akbar", "not_interested"); call("akbar", "no_answer", "legacy1", src="legacy_status")
F.t["activity"] = [dict(employee_id=ids["gio"], summary="Gio booked a meeting with Biz 1", created_at=nowi)]
F.t["profiles"][0]["last_seen"] = nowi
F.t["deals"].append(dict(id="d9", client="X", upfront=500, monthly=0, months=0, closed_at=datetime.now(S.TZ).date().isoformat(), owner_id=ids["james"], version=1, updated_at=F.now()))
F.t["settings"] = [dict(key="daily_targets", value=dict(calls=50, connections=10, meetings=2, sales=1))]
t = akbar.team() if akbar.auth.s else jay2.team()
g = next(p for p in t["people"] if p["name"] == "Gio")
check("gio: 4 calls, 2 connections, 2 prospects, 1 meeting", (g["today"]["calls"], g["today"]["connections"], g["today"]["prospects"], g["today"]["meetings"]) == (4, 2, 2, 1))
check("old imported calls count too (Leafline 11.1)", next(p for p in t["people"] if p["name"] == "Akbar")["today"]["calls"] == 2)
check("company totals add up", (t["totals"]["calls"], t["totals"]["sales"], t["totals"]["meetings"]) == (7, 1, 1))
check("targets and progress come from settings", t["targets"]["calls"] == 50 and g["progress"] == 8 and g["online"] is True)
check("revenue closed today is recorded (Maple 500 + X 500)", t["revenue_today"] == 1000 and t["deals_today"] == 2)
check("activity feed shows who did what", t["activity"][0]["who"] == "Gio" and "booked a meeting" in t["activity"][0]["text"])
check("history covers 14 days incl. today", len(t["series"]) == 14 and t["series"][-1]["calls"] == 7 and t["week"]["calls"] >= 7)
F.down = True; st = jay2.team(); F.down = False
check("offline shows the last numbers, marked stale (nothing invented)", st["stale"] is True and st["totals"]["calls"] == 7)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
