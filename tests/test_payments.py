"""Leafline 11.3: "Confirm payment". A deal payment only counts as money made once someone confirms it.
Desktop engine + sync against the in-memory Supabase, including the 7th migration not being run yet."""
import os, sys, tempfile, time, json
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from datetime import date, datetime, timedelta
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
F.paid_cap = False                                    # start as if the 7th migration has not been run
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

T = datetime.now().date()
past, past2, future = T - timedelta(days=3), T - timedelta(days=33), T + timedelta(days=5)

print("1. pure helpers")
d = dict(id=1, client="X", upfront=500.0, monthly=100.0, months=3, closed_at=past2.isoformat(), first_bill=past2.isoformat(), notes="", confirmed=set())
sm = B.deal_summary(d, T)
check("nothing confirmed: nothing collected, past payments wait for confirmation", sm["collected"] == 0 and sm["unconfirmed"] == 700 and sm["unconfirmed_count"] == 3)
d["confirmed"] = B.conf_set(f"{past2.isoformat()}:upfront,{past2.isoformat()}:monthly,garbage,2026-13-99:upfront")
sm = B.deal_summary(d, T)
check("confirmed payments count, junk keys are ignored", sm["collected"] == 600 and sm["unconfirmed"] == 100 and sm["unconfirmed_count"] == 1)
check("key set only keeps well-formed keys", B.conf_set("2026-11-01:upfront,2026-11-01:bogus,,x") == {"2026-11-01:upfront"})

print("2. desktop engine")
api = B.Api(); api._ready.set()
check("sign in", api.sign_in("gio", "Gio123")["ok"])
check("synced, and the missing 7th migration was noticed", until(lambda: api._sync.status["state"] == "synced" and api._sync.caps.get("paid") is False))
check("deal saved", api.save_deal({"client": "Maple Roofing", "upfront": 1500, "monthly": 99, "months": "", "closed_at": past.isoformat(), "first_bill": future.isoformat()})["ok"])
deal = [x for x in api.get_deals() if x["client"] == "Maple Roofing"][0]
check("get_deals can be sent to the page (no sets left in it)", json.loads(json.dumps(api.get_deals())) and deal["confirmed"] == [])
m = api._money()
check("an unconfirmed payment is not money made", deal["collected"] == 0 and m["all"]["collected"] == 0 and m["all"]["unconfirmed"] == 1500)
check("it shows in the confirmation list", [(p["client"], p["date"], p["kind"]) for p in m["all"]["to_confirm"]] == [("Maple Roofing", past.isoformat(), "upfront")])
check("future payment can't be confirmed", not api.confirm_payment(deal["id"], future.isoformat(), "monthly", True)["ok"])
check("made-up payment can't be confirmed", not api.confirm_payment(deal["id"], (past - timedelta(days=1)).isoformat(), "upfront", True)["ok"])
check("bad kind refused", not api.confirm_payment(deal["id"], past.isoformat(), "bonus", True)["ok"])
check("unknown deal refused", not api.confirm_payment(999999, past.isoformat(), "upfront", True)["ok"])
check("confirm the upfront payment", api.confirm_payment(deal["id"], past.isoformat(), "upfront", True)["ok"])
m = api._money(); deal = [x for x in api.get_deals() if x["client"] == "Maple Roofing"][0]
check("now it counts everywhere", deal["collected"] == 1500 and m["all"]["collected"] == 1500 and m["all"]["unconfirmed"] == 0 and not m["all"]["to_confirm"])
wk = [p for p in m["week"]["payments"] if p["kind"] == "upfront"]
if past >= T - timedelta(days=T.weekday()):
    check("this week's list marks it received", wk and wk[0]["paid"] and wk[0]["due"])
cal = [i for i in api.get_calendar(past.isoformat(), past.isoformat()) if i["src"] == "payment"]
check("calendar shows it as received", cal and cal[0]["paid"] and cal[0]["due"])
check("confirming twice is harmless", api.confirm_payment(deal["id"], past.isoformat(), "upfront", True)["ok"] and api._money()["all"]["collected"] == 1500)
check("editing other fields keeps the confirmation", api.save_deal(dict(deal, notes="website + hosting", months=""))["ok"] and api._money()["all"]["collected"] == 1500)

print("3. sync")
api._sync.kick()
until(lambda: [x for x in F.t["deals"] if x["client"] == "Maple Roofing"])
R = [x for x in F.t["deals"] if x["client"] == "Maple Roofing"]
if not R: print("   outbox:", api._sync.db.execute("SELECT tbl,op,attempts,last_error,blocked FROM outbox").fetchall(), api._sync.status)
check("before the 7th migration the deal still uploads, without the confirmation", len(R) == 1 and "confirmed" not in R[0])
F.paid_cap = True; api._sync.caps["paid"] = None; api._sync.kick()
check("after the migration the confirmation uploads by itself", until(lambda: [x for x in F.t["deals"] if x["client"] == "Maple Roofing"][0].get("confirmed") == f"{past.isoformat()}:upfront"))
check("un-confirm", api.confirm_payment(deal["id"], past.isoformat(), "upfront", False)["ok"] and api._money()["all"]["collected"] == 0)
api._sync.kick()
check("un-confirm uploads", until(lambda: [x for x in F.t["deals"] if x["client"] == "Maple Roofing"][0].get("confirmed") == ""))
rid = R[0]["id"]
for x in F.t["deals"]:
    if x["id"] == rid: x.update(confirmed=f"{past.isoformat()}:upfront", version=x["version"] + 1, updated_at=F.now())
api._sync.kick()
check("a teammate's confirmation comes down", until(lambda: api._money()["all"]["collected"] == 1500))
b = api.get_board()
check("leaderboard data carries the confirmations", b["ok"] and any(x.get("confirmed") == f"{past.isoformat()}:upfront" for x in b["deals"]))

print(f"\n{ok} passed, {fail} failed")
sys.stdout.flush(); os._exit(1 if fail else 0)
