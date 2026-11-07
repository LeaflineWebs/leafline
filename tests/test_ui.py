import os, sys, tempfile, threading, time, json
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
for n in ("gio", "james"): F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee")
import leafline_backend as B
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
api = B.Api(); srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
errs = []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]); pg = br.new_page(viewport={"width": 1440, "height": 900})
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "fonts/" not in m.text and "403" not in m.text else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?t=tok"); pg.wait_for_selector("#login.on", timeout=8000)
    check("login screen shown when signed out", pg.is_visible("#lgForm") and pg.text_content("#syncTx") == "Signed out")
    pg.screenshot(path="/tmp/ui_login.png")
    pg.fill("#lgUser", "gio"); pg.fill("#lgPass", "nope"); pg.click("#lgGo"); pg.wait_for_function("document.querySelector('#lgErr').textContent.length>0")
    check("wrong password shows an error, stays on login", "Wrong username or password" in pg.text_content("#lgErr") and pg.is_visible("#login.on"))
    pg.fill("#lgPass", "Gio123"); pg.click("#lgGo"); pg.wait_for_selector("#pwForm", state="visible", timeout=8000)
    check("first login forces a password change", pg.is_visible("#pwForm") and not pg.is_visible("#lgForm"))
    pg.screenshot(path="/tmp/ui_pw.png")
    pg.fill("#pwNew", "abc"); pg.fill("#pwNew2", "abc"); pg.click("#pwGo"); pg.wait_for_function("document.querySelector('#pwErr').textContent.length>0")
    check("weak password rejected", "8 characters" in pg.text_content("#pwErr"))
    pg.fill("#pwNew", "Gio123"); pg.fill("#pwNew2", "Gio123"); pg.click("#pwGo"); pg.wait_for_timeout(500)
    check("starter password rejected", pg.is_visible("#pwForm"))
    pg.fill("#pwNew", "Leaf!2026x"); pg.fill("#pwNew2", "Leaf!2026x"); pg.click("#pwGo"); pg.wait_for_selector("#login.on", state="detached", timeout=8000)
    check("password changed in shared auth", F.users["gio@leaflineweb.com"]["pw"] == "Leaf!2026x")
    pg.wait_for_function("document.querySelector('#hiTxt').textContent.includes('Gio')", timeout=8000)
    check("greeting shows the signed-in employee", "Gio" in pg.text_content("#hiTxt"))
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=15000)
    check("sync chip says Synced", True)
    with api._lock:
        api._db.execute("INSERT INTO leads(id,name,phone,pdigits,btype,search,status,added_at) VALUES('ui1','UI Test Roofing','+1-519-555-0777','5195550777','Roofing','Roofing | Kitchener','none','2026-11-06 10:00')"); api._db.commit()
    api._sync.kick(); t0 = time.time()
    while time.time() - t0 < 15 and not any(r["id"] == "ui1" for r in F.t["leads"]): time.sleep(.3)
    check("a lead created in the app reaches the shared database", any(r["id"] == "ui1" and r["added_by"] == F.users["gio@leaflineweb.com"]["uid"] for r in F.t["leads"]))
    F.t["leads"].append(dict(id="remote1", name="Added by James", phone="+1-226-555-0001", phone_key="2265550001", owner_name="N/A", email="N/A", rating="N/A", reviews="N/A", website="N/A", address="N/A", search="Roofing | Kitchener", btype="Roofing", hours="", status="none", notes="", enriched=False, added_at=None, called_at=None, meeting_at=None, version=1, updated_at=F.now(), created_at=F.now()))
    api._sync.kick(); t0 = time.time()
    while time.time() - t0 < 15 and not api._db.execute("SELECT 1 FROM leads WHERE id='remote1'").fetchone(): time.sleep(.3)
    check("a lead added by James appears in Gio's app automatically", api._db.execute("SELECT 1 FROM leads WHERE id='remote1'").fetchone() is not None)
    pg.screenshot(path="/tmp/ui_dash.png")
    from datetime import datetime, timezone
    nowi = datetime.now(timezone.utc).isoformat(); gid = F.users["gio@leaflineweb.com"]["uid"]; jid = F.users["james@leaflineweb.com"]["uid"]
    for o in ("no_answer", "interested", "meeting_booked"): F.t["call_log"].append(dict(id=o, employee_id=gid, lead_id="ui1", outcome=o, started_at=nowi, source="app", version=1))
    F.t["call_log"].append(dict(id="s1", employee_id=jid, lead_id="remote1", outcome="sale_completed", started_at=nowi, source="app", version=1))
    F.t["activity"].append(dict(employee_id=gid, summary="Gio booked a meeting with UI Test Roofing", created_at=nowi))
    pg.click("#nav [data-go=team]"); pg.wait_for_selector(".tm-p", timeout=10000)
    txt = pg.inner_text("#pg-team")
    check("team page lists every active employee with live numbers", "Gio" in txt and "James" in txt and pg.locator(".tm-p").count() == 2)
    check("totals: 4 calls, 1 meeting, 1 sale; activity feed shown", pg.locator(".tm-tile b").nth(0).inner_text() == "4" and pg.locator(".tm-tile b").nth(3).inner_text() == "1" and "booked a meeting" in txt)
    check("signed-in employee's card is highlighted", "Gio" in pg.locator(".tm-p.me h3").inner_text())
    pg.screenshot(path="/tmp/ui_team.png")
    pg.click("#nav [data-go=calendar]"); pg.wait_for_timeout(600)
    pg.evaluate("eventModal(null,'2026-11-12')"); pg.wait_for_selector("#evWho", timeout=5000)
    opts = pg.eval_on_selector_all("#evWho option", "o=>o.map(x=>x.textContent)")
    check("event dialog lists employees to assign to (you marked)", any("Gio (you)" in o for o in opts) and any(o == "James" for o in opts))
    pg.fill("#evTitle", "Demo for Maple"); pg.select_option("#evWho", jid); pg.screenshot(path="/tmp/ui_event.png"); pg.click("[data-save]")
    t0 = time.time()
    while time.time() - t0 < 15 and not any(e["title"] == "Demo for Maple" for e in F.t["events"]): api._sync.kick(); time.sleep(.4)
    ev = next((e for e in F.t["events"] if e["title"] == "Demo for Maple"), None)
    check("event reached shared db: assigned to James, created by Gio", ev is not None and ev["assigned_to"] == jid and ev["created_by"] == gid)
    items = api.get_calendar("2026-11-01", "2026-11-30"); mine = [i for i in items if i["title"] == "Demo for Maple"]
    check("calendar shows assignee and creator names", mine and mine[0]["assigned_name"] == "James" and mine[0]["created_name"] == "Gio")
    pg.click("#nav [data-go=dash]"); pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_function("document.querySelector('#hiTxt').textContent.includes('Gio')", timeout=8000)
    check("reload keeps the session (no login again)", not pg.is_visible("#login.on"))
    F.down = True; api._sync.kick(); pg.wait_for_function("document.querySelector('#syncTx').textContent.startsWith('Offline')", timeout=15000)
    check("offline is shown", True)
    F.down = False
    api._sync.kick(); pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=40000)
    check("recovers to Synced when connection returns", True)
    pg.click("#outBtn"); pg.wait_for_selector("#login.on", timeout=8000)
    check("sign out returns to the login screen; session file removed", not os.path.exists(os.path.join(os.path.dirname(B.PROFILE), "session.json")))
    pg.fill("#lgUser", "james"); pg.fill("#lgPass", "James123"); pg.click("#lgGo"); pg.wait_for_selector("#pwForm", state="visible", timeout=8000)
    check("a second employee can sign in on the same PC after sync", True)
    check("no console errors", not errs)
    if errs: print(errs[:5])
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
