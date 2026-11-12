"""11.16: call reminders. Set one from Find Leads (with the owner, call notes and company details), see it behind the
clock button in the top bar, get the 'Today's reminders' pop-up when the app opens, and a notification in the top right
when one comes due. Runs the real WEBSITE build (PC and phone sizes) and the PC app's engine against the fake shared
database, with the reminder functions running on a REAL Postgres with the real migrations (tests/pg/server.mjs)."""
import os, sys, tempfile, threading, http.server, functools, time
from datetime import datetime, timedelta, timezone
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
import msg_harness
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
F.t["leads"].append(dict(id="r1", name="Maple Roofing", phone="(519) 555-0101", owner_name="N/A", email="N/A", rating="4.6", reviews="38", website="https://maple.ca",
                         address="1 King St, London ON", search="Roofing | London", btype="Roofing", hours="", status="none", notes="", enriched=False,
                         added_at="2026-10-01T14:00:00+00:00", called_at=None, meeting_at=None, called_by=None, version=1, updated_at=F.now(), created_at=F.now(), phone_key="5195550101"))
F.t["leads"].append(dict(id="r2", name="Oak Plumbing", phone="(519) 555-0102", owner_name="Dana", email="N/A", rating="4.1", reviews="12", website="N/A",
                         address="2 Queen St, London ON", search="Plumbing | London", btype="Plumbing", hours="", status="yellow", notes="Wants a quote", enriched=False,
                         added_at="2026-10-01T14:00:00+00:00", called_at="2026-11-10T15:00:00+00:00", meeting_at=None, called_by=ids["gio"], version=1, updated_at=F.now(), created_at=F.now(), phone_key="5195550102"))
F.msg_url = msg_harness.start_pg_server()
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
def page(br, who, phone=False, q=""):
    o = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=UA) if phone else dict(viewport={"width": 1440, "height": 900})
    ctx = br.new_context(**o); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto(f"http://127.0.0.1:{port}/?nointro{q}"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    return ctx, pg, errs
def relog(pg, q):
    pg.goto(f"http://127.0.0.1:{port}/?nointro{q}"); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
rpc = lambda pg, fn, a: pg.evaluate("async([f,a])=>api('sb_rpc',f,a)", [fn, a])
clear = lambda pg: pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
iso = lambda d: d.astimezone(timezone.utc).isoformat()

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    print("1. setting a reminder from Find Leads (PC size)")
    ctx, pg, errs = page(br, "gio")
    clear(pg)
    check("there's a reminders button in the top bar, next to the script button", pg.is_visible("#remBtn") and pg.evaluate("()=>document.querySelector('#remBtn').previousElementSibling.id")=="scriptBtn")
    pg.evaluate("async()=>{await go('find',true);S.active='r1';lastDetail=null;renderFind()}"); pg.wait_for_selector("#detail #dRem")
    pg.fill("#dOwner", "Sam Lee"); pg.wait_for_timeout(1500); pg.fill("#dNotes", "Interested in a new website. Call back after the 20th, ask for Sam."); pg.wait_for_timeout(400)
    pg.click("#dRem"); pg.wait_for_selector(".ov.on #rmAt")
    txt = pg.inner_text(".ov.on")
    check("the reminder starts with the business, phone and address", all(x in txt for x in ["Maple Roofing", "(519) 555-0101", "1 King St"]))
    check("...and the owner and the call notes you just typed", pg.input_value("#rmOwner") == "Sam Lee" and "after the 20th" in pg.input_value("#rmNotes"))
    pg.click(".ov.on [data-q=tm]")
    want = pg.input_value("#rmAt")
    check(f"'Tomorrow 9 am' fills in the time ({want})", want.endswith("T09:00"))
    pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(600)
    lst = pg.evaluate("()=>REM.list")
    check("it's saved with the company details, owner and notes", len(lst) == 1 and lst[0]["company"] == "Maple Roofing" and lst[0]["owner_name"] == "Sam Lee" and "ask for Sam" in lst[0]["notes"] and lst[0]["website"] == "https://maple.ca")
    lead = next(l for l in F.t["leads"] if l["id"] == "r1")
    check("the owner and notes are also saved on the business", lead["owner_name"] == "Sam Lee" and "after the 20th" in lead["notes"])
    pg.click("#remBtn"); pg.wait_for_selector("#remPanel.on .remr")
    check("the top-bar list shows it under 'Coming up'", "coming up" in pg.inner_text("#remPanel").lower() and "Maple Roofing" in pg.inner_text("#remPanel"))
    pg.click("#remPanel .remr"); pg.wait_for_selector(".ov.on .remd .rem-kv")
    t = pg.inner_text(".ov.on")
    check("opening it shows everything saved", all(x in t for x in ["Maple Roofing", "Sam Lee", "(519) 555-0101", "Roofing", "1 King St", "maple.ca", "after the 20th"]))
    clear(pg)

    print("2. a notification in the top right when one is due")
    soon = datetime.now(timezone.utc) + timedelta(seconds=8)
    rpc(pg, "rem_save", {"p": {"remind_at": iso(soon), "company": "Cedar Dental", "owner_name": "Dr. Patel", "phone": "519-555-0103", "notes": "Follow up on the logo"}})
    pg.evaluate("()=>loadRem(true)")
    pg.wait_for_selector(".remn", timeout=45000)
    box = pg.evaluate("()=>{const r=document.querySelector('.remn').getBoundingClientRect();return [r.top,r.right,innerWidth]}")
    check(f"it appears in the top right ({box})", box[0] < 60 and box[2] - box[1] < 40)
    n = pg.inner_text(".remn")
    check("it says which business, who to ask for, and the notes", "Cedar Dental" in n and "Dr. Patel" in n and "logo" in n)
    pg.wait_for_timeout(16000)
    check("it doesn't repeat", pg.locator(".remn").count() == 1)
    check("the top-bar button shows one for today", pg.inner_text("#remCnt") == "1" and pg.evaluate("()=>document.querySelector('#remCnt').classList.contains('on')"))
    pg.click(".remn [data-n=done]"); pg.wait_for_timeout(1200)
    check("Done ticks it off and closes the notification", pg.locator(".remn").count() == 0 and any(r["company"] == "Cedar Dental" and r["done_at"] for r in pg.evaluate("()=>REM.list")))
    check("no page errors (PC)", not errs or print(errs))
    ctx.close()

    print("3. the pop-up when you open the app on the day")
    ctx, pg, errs2 = page(br, "gio", q="&rem")
    now = datetime.now(timezone.utc)
    rpc(pg, "rem_save", {"p": {"remind_at": iso(now - timedelta(minutes=30)), "company": "Birch Auto", "notes": "Call about the wrap"}})
    later = now + timedelta(minutes=2)
    rpc(pg, "rem_save", {"p": {"remind_at": iso(later), "company": "Pine Spa", "owner_name": "Lee"}})
    relog(pg, "&rem")
    pg.wait_for_selector(".ov.on .remlist", timeout=30000)
    t = pg.inner_text(".ov.on")
    check("opening the app shows today's reminders (one already due, one later today)", "Today's reminders" in t and "Birch Auto" in t and "Pine Spa" in t)
    check("...but not tomorrow's", "Maple Roofing" not in t)
    check("reminders that were due before you opened the app don't also pop up as notifications", pg.locator(".remn").count() == 0)
    pg.click(".ov.on [data-rem]:has-text('Birch Auto')"); pg.wait_for_selector(".ov.on .remd .rem-nt")
    check("tapping one opens it with its notes", "Call about the wrap" in pg.inner_text(".ov.on"))
    pg.click(".ov.on [data-a=s1]"); pg.wait_for_timeout(1000)
    r = next(x for x in pg.evaluate("()=>REM.list") if x["company"] == "Birch Auto")
    check("'In 1 hour' snoozes it", datetime.fromisoformat(r["remind_at"]) > datetime.now(timezone.utc) + timedelta(minutes=55))
    check("no page errors (pop-up)", not errs2 or print(errs2))
    ctx.close()

    print("4. private, and on a phone")
    ctx, pg, errs3 = page(br, "tim", phone=True)
    clear(pg)
    check("Tim doesn't see Gio's reminders", pg.evaluate("async()=>(await loadRem(true)).length") == 0)
    check("the reminders button is in the phone's top bar", pg.is_visible("#remBtn"))
    pg.tap("#remBtn"); pg.wait_for_selector("#remPanel.on")
    check("an empty list explains how to set one", "Set reminder" in pg.inner_text("#remPanel"))
    fits = pg.evaluate("()=>{const r=document.querySelector('#remPanel').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth}")
    check("the list fits on the phone screen", fits)
    pg.tap("#title"); pg.wait_for_timeout(300)
    pg.evaluate("async()=>{await go('called',true)}"); pg.wait_for_timeout(800)
    pg.evaluate("()=>leadModal(S.called.find(l=>l.id==='r2'))"); pg.wait_for_selector(".ov.on [data-rem]")
    check("a business pop-up on Called Leads has 'Set reminder' too", pg.is_visible(".ov.on [data-rem]"))
    pg.tap(".ov.on [data-rem]"); pg.wait_for_selector(".ov.on #rmAt")
    check("...filled in with that business's owner and notes", pg.input_value("#rmOwner") == "Dana" and pg.input_value("#rmNotes") == "Wants a quote")
    check("nothing sticks out sideways on the phone", pg.evaluate("()=>{const d=document.querySelector('.ov.on .dlg').getBoundingClientRect();return d.left>=0&&d.right<=innerWidth+1}"))
    pg.tap(".ov.on [data-q='1h']"); pg.tap(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    check("Tim's reminder is saved, just for him", [r["company"] for r in pg.evaluate("()=>REM.list")] == ["Oak Plumbing"])
    check("no page errors (phone)", not errs3 or print(errs3))
    ctx.close()

    print("5. before the 15th database update")
    url, F.msg_url = F.msg_url, None
    ctx, pg, errs4 = page(br, "gio")
    clear(pg); pg.evaluate("async()=>{REM.at=0;await loadRem(true)}"); pg.click("#remBtn"); pg.wait_for_timeout(500)
    check("the list explains the update is needed", "15th database update" in pg.inner_text("#remPanel"))
    pg.evaluate("async()=>{await go('find',true);S.active='r1';lastDetail=null;renderFind()}"); pg.wait_for_selector("#detail #dRem"); pg.click("#dRem"); pg.wait_for_selector(".ov.on #rmAt")
    pg.click(".ov.on [data-ok]"); pg.wait_for_timeout(800)
    check("setting one says so instead of failing silently", "15th database update" in pg.inner_text("#rmErr"))
    check("no page errors (old database)", not errs4 or print(errs4))
    ctx.close(); F.msg_url = url

    print("6. the PC app (desktop engine)")
    os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
    import leafline_backend as B
    api = B.Api(db=B.open_db(os.path.join(os.environ["HOME"], "t.db")), profile_path=os.path.join(os.environ["HOME"], "p.json")); api._ready.set()
    assert api.sign_in("gio", "Gio123")["ok"]
    t0 = time.time()
    while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.3)
    r = api.sb_rpc("rem_list", {})
    check("the PC app reads Gio's reminders through the same database", r.get("ok") and any(x["company"] == "Maple Roofing" for x in r["data"]))
    api._sync.stop.set()
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
