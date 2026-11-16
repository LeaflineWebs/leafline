"""11.19 productivity pack: automatic follow-ups, the duplicate / do-not-call guard, lead scores, saved searches, the
Pipeline page and the admin System health card. Runs the real WEBSITE build (PC and phone sizes) and the PC app's engine
against the fake shared database; reminders run on a REAL Postgres (tests/pg/server.mjs). The database rules of the
17th update are tested in tests/pg/test_pipeline_health_sql.mjs."""
import os, sys, tempfile, threading, http.server, functools, time, uuid
from datetime import datetime, timedelta, timezone
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
import msg_harness
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
NOW = datetime.now(timezone.utc); iso = lambda d: d.isoformat()
def lead(i, name, phone, status="none", web="N/A", reviews="N/A", rating="N/A", by=None, ago=None, owner="N/A"):
    F.t["leads"].append(dict(id=i, name=name, phone=phone, owner_name=owner, email="N/A", rating=rating, reviews=reviews, website=web, address="1 King St, London ON",
        search="Shops | London", btype="Shop", hours="", status=status, notes="", enriched=False, added_at=iso(NOW - timedelta(days=30)),
        called_at=iso(NOW - timedelta(days=ago)) if ago is not None else None, meeting_at=None, called_by=by and ids[by], version=1, updated_at=F.now(), created_at=F.now(),
        phone_key="".join(c for c in phone if c.isdigit())[-10:]))
def call(who, lid, phone, outcome, days):
    u = str(uuid.uuid4()); F.t["call_log"].append(dict(id=u, client_op_id=u, lead_id=lid, employee_id=ids[who], phone=phone, started_at=iso(NOW - timedelta(days=days)),
        outcome=outcome, notes="", source="app", credited_to=None, created_at=F.now()))
# to call
lead("L1", "Maple Roofing", "(519) 555-0101", reviews="3", rating="4.8", owner="Sam Lee")     # best prospect; Tim called 2 days ago
lead("L2", "Oak Plumbing", "519-555-0102", web="https://oak.ca", reviews="250", rating="4.1")  # said not interested (phone only)
lead("L3", "Cedar Cafe", "519-555-0103", reviews="40", rating="3.2")
lead("L4", "Elm Auto", "519-555-0104", reviews="12", rating="4.4")
call("tim", "L1", "(519) 555-0101", "no_answer", 2); call("james", None, "+1 519 555 0102", "not_interested", 40)
# already called (Pipeline)
lead("P1", "Birch Dental", "519-555-0201", "green", by="gio", ago=1); lead("P2", "Pine Spa", "519-555-0202", "yellow", by="tim", ago=10)
lead("P3", "Ash Bakery", "519-555-0203", "orange", by="gio", ago=0); lead("P4", "Fir Gym", "519-555-0204", "red", by="tim", ago=3)
lead("P5", "Spruce Law", "519-555-0205", "yellow", by="gio", ago=2)
F.t["deals"].append(dict(id="d0000000-0000-4000-8000-0000000000e1", client="Spruce Law", upfront=900, monthly=0, months=0, closed_at=NOW.date().isoformat(), first_bill=NOW.date().isoformat(),
                         notes="", owner_id=ids["gio"], confirmed="", version=1, updated_at=F.now(), created_at=F.now()))
F.msg_url = msg_harness.start_pg_server()
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c, extra=None):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l, "" if extra is None else str(extra)[:400])
errs = []
def page(br, who, phone=False):
    o = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True) if phone else dict(viewport={"width": 1440, "height": 900})
    ctx = br.new_context(**o); pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300])); pg.on("dialog", lambda d: d.accept())
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())"); pg.wait_for_timeout(300)
    return ctx, pg
rem_list = lambda pg: pg.evaluate("async()=>{const r=await api('sb_rpc','rem_list',{});return r.ok?r.data:r}")

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    ctx, pg = page(br, "gio")

    print("1. Lead scores")
    pg.evaluate("async()=>{await go('find',true);$('#scope').value='all';$('#scope').dispatchEvent(new Event('change'))}"); pg.wait_for_timeout(1500)
    check("Sort has 'Best prospects' (added last, so the current sort doesn't change)", pg.evaluate("()=>{const s=$('#sort');return s.options[s.options.length-1].value==='score'&&s.value!=='score'}"))
    pg.select_option("#sort", "score"); pg.wait_for_timeout(600)
    order = pg.evaluate("()=>[...document.querySelectorAll('#list .li b')].map(b=>b.textContent)")
    check(f"Best prospects puts Maple Roofing (no website, 3 reviews, 4.8★, owner known) first and Oak Plumbing (website, 250 reviews) last ({order})", order[:1] == ["Maple Roofing"] and order[-1:] == ["Oak Plumbing"])
    sc = pg.evaluate("()=>Object.fromEntries([...document.querySelectorAll('#list .li')].map(n=>[n.querySelector('b').textContent,+n.querySelector('.sc-pill').textContent]))")
    check(f"every row shows its score ({sc})", sc.get("Maple Roofing", 0) >= 70 and sc.get("Oak Plumbing", 100) < 45)
    pg.evaluate("()=>{S.active='L1';lastDetail=null;renderFind()}"); pg.wait_for_timeout(300)
    check("the detail panel explains the score", all(t.lower() in pg.inner_text("#detail").lower() for t in ("Prospect score", "No website", "Very few reviews (3)", "Great rating (4.8★)", "Owner's name known")))

    print("2. Called-recently / not-interested warnings")
    pg.wait_for_function("()=>document.querySelector('#list .li[data-id=\"L1\"] .gd-ic')&&document.querySelector('#list .li[data-id=\"L2\"] .gd-ic.dnc')", timeout=40000)
    check("Maple Roofing (Tim called 2 days ago) and Oak Plumbing (said not interested) are flagged in the list", not pg.query_selector('#list .li[data-id="L3"] .gd-ic'))
    pg.evaluate("()=>{lastDetail=null;renderDetail()}"); pg.wait_for_timeout(200)
    check("the detail panel says who called and what happened", "Tim called 2 days ago (No answer)" in pg.inner_text("#detail .gd-ban"))
    pg.click("#detail .fact a.tel"); pg.wait_for_selector(".ov.on [data-ok]")
    check("pressing Call asks first", "Called recently" in pg.inner_text(".ov.on") and "Maple Roofing" in pg.inner_text(".ov.on"))
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    pg.click("#detail .fact a.tel"); pg.wait_for_selector(".ov.on [data-ok]"); pg.click(".ov.on [data-ok]"); pg.wait_for_timeout(700)
    check("'Call anyway' goes ahead (on a PC the number is copied)", not pg.query_selector(".ov.on [data-ok]"))
    pg.click("#detail .fact a.tel"); pg.wait_for_timeout(500)
    check("...and it doesn't ask again for the next 10 minutes", not pg.query_selector(".ov.on [data-ok]"))
    pg.evaluate("()=>{S.active='L2';lastDetail=null;renderFind()}"); pg.wait_for_timeout(300)
    check("Oak Plumbing: 'James was told not interested'", "James was told \"not interested\" 40 days ago" in pg.inner_text("#detail .gd-ban"))

    print("3. Automatic follow-ups")
    pg.evaluate("async()=>{S.active='L4';lastDetail=null;renderFind();await markLeads('orange')}"); pg.wait_for_timeout(4500)
    rl = rem_list(pg); r = next((x for x in rl if x.get("company") == "Elm Auto"), None) if isinstance(rl, list) else None
    if r:
        at = datetime.fromisoformat(r["remind_at"].replace("Z", "+00:00")).astimezone()
        check(f"No answer sets a reminder for the next workday ({at:%a %H:%M})", at.date() > datetime.now().date() and at.weekday() < 5 and (at - datetime.now().astimezone()).days <= 3)
        check("...at a different time of day than this call", (at.hour == 14) == (datetime.now().hour < 12) and at.hour in (10, 14))
        check("...with the business's details", r.get("phone") == "519-555-0104" and r.get("btype") == "Shop")
    else: check("No answer sets a reminder", False, rl)
    check("a toast says when, with Undo", "Follow-up set for" in pg.evaluate("()=>document.querySelector('#toast').innerText"))
    n0 = len(rem_list(pg))
    pg.evaluate("async()=>{await autoFollow('no_answer',[S.called.find(x=>x.id==='L4')||{id:'L4',name:'Elm Auto',phone:'519-555-0104'}])}"); pg.wait_for_timeout(1500)
    check("a business that already has a follow-up doesn't get a second one", len(rem_list(pg)) == n0)
    pg.evaluate("async()=>{S.active='L3';lastDetail=null;renderFind();await markLeads('yellow')}"); pg.wait_for_selector(".ov.on #rmAt", timeout=10000)
    check("Interested opens the reminder pop-up for that business", "Cedar Cafe" in pg.inner_text(".ov.on"))
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    pg.evaluate("async()=>{await go('account',true)}"); pg.wait_for_selector("#afTgl")
    check("Settings has a Calling card with the switch on", pg.get_attribute("#afTgl", "aria-checked") == "true")
    pg.click("#afTgl"); pg.wait_for_timeout(300)
    check("switching it off is saved", pg.evaluate("()=>getP('autoFollow',true)===false&&$('#afTgl').getAttribute('aria-checked')==='false'"))
    n1 = len(rem_list(pg))
    pg.evaluate("async()=>{await go('find',true);S.active='L2';lastDetail=null;renderFind();await markLeads('orange')}"); pg.wait_for_timeout(3500)
    check("with it off, No answer doesn't set a reminder", len(rem_list(pg)) == n1)
    pg.evaluate("()=>setP('autoFollow',true)")

    print("4. Saved searches")
    pg.evaluate("async()=>{await go('find',true)}"); pg.wait_for_timeout(500)
    for k, v in (("fCountry", "Canada"), ("fState", "Ontario"), ("fCity", "London"), ("fType", "Roofing")): pg.fill("#" + k, v)
    pg.click("#ssAdd"); pg.wait_for_timeout(300)
    ss = pg.evaluate("()=>getP('savedSearches',[])")
    check("Save this search keeps the area and business type", len(ss) == 1 and ss[0]["type"] == "Roofing" and ss[0]["city"] == "London" and ss[0]["last"] == 0)
    check("it shows as a chip, due (never run)", "Roofing in London, Ontario, Canada" in pg.inner_text("#ssBar") and pg.query_selector("#ssBar .ss-chip.due"))
    pg.click("#ssAdd"); pg.wait_for_timeout(200)
    check("saving the same search twice is refused", len(pg.evaluate("()=>getP('savedSearches',[])")) == 1)
    for k in ("fCountry", "fState", "fCity", "fType"): pg.fill("#" + k, "")
    pg.evaluate("()=>{window.__ran=0;window.startSearch=()=>{window.__ran++}}")
    pg.click("#ssBar .ss-run"); pg.wait_for_timeout(400)
    check("one click fills the form and runs it", pg.evaluate("()=>window.__ran===1&&$('#fType').value==='Roofing'&&$('#fCity').value==='London'"))
    pg.evaluate("()=>onPy({e:'search_done',d:{n:4,q:'Roofing | London'}})"); pg.wait_for_timeout(400)
    ss = pg.evaluate("()=>getP('savedSearches',[])")
    check("when it finishes, it remembers when and how many new businesses (4)", ss[0]["lastNew"] == 4 and ss[0]["last"] > 0 and "4 new" in pg.inner_text("#ssBar"))
    check("...and it isn't due again until next week", not pg.query_selector("#ssBar .ss-chip.due"))
    pg.evaluate("()=>{const L=getP('savedSearches',[]);L[0].last=Date.now()-8*864e5;setP('savedSearches',L);ssPaint();ssNudged=false}"); pg.wait_for_timeout(6800)
    check("after 7 days it's due again, and Leafline offers to run it", pg.query_selector("#ssBar .ss-chip.due") and "due for their weekly refresh" in pg.evaluate("()=>document.querySelector('#toast').innerText"))
    pg.click("#ssBar .ss-x"); pg.wait_for_timeout(200)
    check("× removes it", pg.evaluate("()=>getP('savedSearches',[]).length") == 0)

    print("5. Pipeline")
    pg.evaluate("async()=>{await reload();await go('pipeline',true)}"); pg.wait_for_selector("#pg-pipeline .pl-col", timeout=20000); pg.wait_for_timeout(800)
    cols = pg.evaluate("()=>Object.fromEntries([...document.querySelectorAll('#pg-pipeline .pl-col')].map(c=>[c.dataset.col,[...c.querySelectorAll('.pl-card b')].map(b=>b.textContent).sort()]))")
    check(f"the six columns, worked out from the call results ({cols})", cols.get("meeting") == ["Birch Dental"] and "Pine Spa" in cols.get("interested", []) and "Ash Bakery" in cols.get("called", [])
          and cols.get("lost") == ["Fir Gym"] and cols.get("proposal") == [])
    check("a business with a closed deal shows as Won", cols.get("won") == ["Spruce Law"])
    check("businesses still to call aren't on it", not any("Maple Roofing" in v for v in cols.values()))
    pg.screenshot(path=os.path.join(os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp(), "pipeline.png"))
    check("Pine Spa (no change for 10 days) is marked Stale", pg.evaluate("()=>{const c=document.querySelector('.pl-card[data-pl=\"P2\"]');return !!(c&&c.querySelector('.pl-stale'))}"))
    pg.select_option('.pl-card[data-pl="P2"] .pl-mv', "proposal"); pg.wait_for_timeout(1500)
    check("moving Pine Spa to Proposal sent saves it for the team", any(r["lead_id"] == "P2" and r["stage"] == "proposal" for r in F.t["lead_stages"]))
    check("...shows it there, marked 'Moved', and no longer stale", pg.evaluate("()=>{const c=document.querySelector('.pl-col[data-col=\"proposal\"] .pl-card[data-pl=\"P2\"]');return !!(c&&c.querySelector('.pl-hand')&&!c.querySelector('.pl-stale'))}"))
    check("...and Activity says who moved it", any(a["summary"] == "Gio moved Pine Spa to Proposal sent" for a in F.t["activity"]))
    pg.evaluate("()=>plMove('P2','interested')"); pg.wait_for_timeout(1200)
    check("moving it back to where its result puts it clears the hand-made stage", not any(r["lead_id"] == "P2" for r in F.t["lead_stages"]))
    pg.click('#pg-pipeline [data-plm="1"]'); pg.wait_for_timeout(500)
    mine = pg.evaluate("()=>[...document.querySelectorAll('#pg-pipeline .pl-card b')].map(b=>b.textContent)")
    check(f"'Mine' shows only Gio's ({sorted(mine)})", "Birch Dental" in mine and "Pine Spa" not in mine and "Fir Gym" not in mine)
    pg.click('#pg-pipeline [data-plm="0"]'); pg.click("#plStale"); pg.wait_for_timeout(500)
    check("'Stale only' shows just the stale ones", pg.evaluate("()=>[...document.querySelectorAll('#pg-pipeline .pl-card b')].map(b=>b.textContent)") == ["Pine Spa"])
    pg.click("#plStale"); pg.wait_for_timeout(300)
    check("Pipeline is in the sidebar", pg.query_selector('.side [data-go="pipeline"]') is not None)
    pg.evaluate("async()=>{await reportStatus(true)}"); pg.wait_for_timeout(500)
    check("the app reports its version and sync state", any(r["user_id"] == ids["gio"] and r["version"] and r["platform"] == "web" for r in F.t["app_status"]))
    ctx.close()

    print("6. System health (admins)")
    ctx, pg = page(br, "tim"); pg.evaluate("async()=>{await go('admin',true)}"); pg.wait_for_timeout(2500)
    check("Tim (not an admin) doesn't get it", not pg.query_selector("#hlCard"))
    r = pg.evaluate("async()=>await api('sb_rpc','team_health',{})"); check("...and the database refuses him directly", not r.get("ok"))
    ctx.close()
    ctx, pg = page(br, "james"); pg.evaluate("async()=>{await reportStatus(true);await go('admin',true)}"); pg.wait_for_selector("#hlCard .hl-tbl", timeout=30000)
    pg.evaluate("()=>document.querySelector('#hlCard').scrollIntoView({block:'start'})"); pg.wait_for_timeout(400); pg.screenshot(path=os.path.join(os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp(), "health.png"))
    txt = pg.inner_text("#hlCard")
    check("James sees every database update as run", "Every database update has been run" in txt and len(pg.query_selector_all("#hlCard .hl-up")) == 16 and not pg.query_selector("#hlCard .hl-up.no"))
    check("...and each person's app version and sync", "Gio" in txt and "website" in txt and "Not reported yet" in txt)
    F.split_cap = False; pg.click("#hlRe"); pg.wait_for_function("()=>document.querySelector('#hlCard .hl-up.no')", timeout=20000)
    check("a missing update is called out with what to do", "Database update 16 has not been run" in pg.inner_text("#hlCard") and "RUN_IN_SUPABASE.sql" in pg.inner_text("#hlCard"))
    F.split_cap = True; ctx.close()

    print("7. Phone size")
    ctx, pg = page(br, "gio", phone=True)
    pg.evaluate("async()=>{await go('pipeline',true)}"); pg.wait_for_selector("#pg-pipeline .pl-col", timeout=20000); pg.wait_for_timeout(600)
    pg.screenshot(path=os.path.join(os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp(), "pipeline_phone.png"))
    check("the Pipeline scrolls sideways inside itself, not the whole page", pg.evaluate("()=>document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.pl-cols').scrollWidth>innerWidth"))
    pg.evaluate("()=>openSheet()"); pg.wait_for_timeout(500)
    check("Pipeline is in the More sheet", pg.evaluate("()=>!!document.querySelector('#sheetGrid [data-go=\"pipeline\"]')"))
    ctx.close()

    print("8. Before the 17th database update")
    F.p17_cap = False
    ctx, pg = page(br, "gio")
    pg.evaluate("async()=>{await go('pipeline',true)}"); pg.wait_for_selector("#pg-pipeline .pl-col", timeout=20000); pg.wait_for_timeout(500)
    check("the Pipeline still works from the call results, and says moving cards needs the update", "needs the 17th database update" in pg.inner_text("#pg-pipeline") and pg.query_selector('.pl-col[data-col="meeting"] .pl-card'))
    pg.evaluate("async()=>{await go('find',true);$('#scope').value='all';$('#scope').dispatchEvent(new Event('change'))}"); pg.wait_for_timeout(2500)
    check("Find Leads works without the call warnings (nothing breaks)", pg.query_selector("#list .li") and not pg.query_selector("#list .gd-ic"))
    ctx.close(); F.p17_cap = True

    print("9. The PC app (desktop engine)")
    os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
    import leafline_backend as B
    api = B.Api(db=B.open_db(os.path.join(os.environ["HOME"], "t.db")), profile_path=os.path.join(os.environ["HOME"], "p.json")); api._ready.set()
    assert api.sign_in("gio", "Gio123")["ok"]
    t0 = time.time()
    while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.3)
    r = api.sb_rpc("lead_guard", {"p_leads": [{"id": "L1", "key": "5195550101"}]})
    check("the PC app gets the call warnings through the same database", r.get("ok") and r["data"] and r["data"][0]["last_name"] == "Tim", r)
    r = api.sb_rpc("lead_stage_set", {"p_lead": "P1", "p_stage": "proposal"})
    check("...and can move pipeline cards", r.get("ok") and any(x["lead_id"] == "P1" for x in F.t["lead_stages"]), r)
    r = api.sb_rpc("me_status_report", {"p": {"version": "11.19.0", "platform": "desktop", "sync_state": "synced", "pending": 0}})
    check("...and report its status", r.get("ok"), r)
    api._sync.stop.set()
    check("no page errors", not errs, errs[:3])
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
