"""11.10: company costs. Admins add/remove them on Profits; everyone sees them; each is taken off the money made that
month (Profits, Dashboard) and off the leaderboard money of the person it's charged to."""
import os, sys, tempfile, threading, time
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from datetime import date
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "james", "tim")}
for p in F.t["profiles"]: p["must_change_password"] = False
TODAY = date.today().isoformat()
# Gio closed a $500 deal today and the payment is confirmed, so $500 counts as made this month
F.t["deals"].append(dict(id="d0000000-0000-4000-8000-0000000000a1", client="Maple Roofing", upfront=500, monthly=0, months=0, closed_at=TODAY, first_bill=TODAY,
                         notes="", owner_id=ids["gio"], confirmed=f"{TODAY}:upfront", version=1, updated_at=F.now(), created_at=F.now()))
import leafline_backend as B
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)

api = B.Api(); api._ready.set()
srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
MADE = "()=>{const s=[...document.querySelectorAll('#pg-profits .stat')].find(e=>/Made in/.test(e.innerText));return s.querySelector('.vl').innerText.replace(/\\s/g,'')}"
BOARD = "(id)=>{const e=document.querySelector(`#lbBody [data-lbid=\"${id}\"] .v`);return e&&e.innerText.replace(/\\s/g,'')}"

def signin(pg, who):
    pg.goto(f"http://127.0.0.1:{port}/?t=tok&nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.press("#lgPass", "Enter")
    pg.wait_for_function(f"typeof S!=='undefined'&&S.ready&&S.me&&S.me.username==='{who}'", timeout=60000)
    t0 = time.time()
    while api._sync.status["state"] != "synced" and time.time() - t0 < 20: time.sleep(.2)
    pg.evaluate("async()=>{await reload()}"); pg.wait_for_timeout(600)

def money_page(pg):
    pg.evaluate("async()=>{COSTS.at=0;await loadCosts(true);await go('dash');await go('profits')}"); pg.wait_for_timeout(2200)

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    signin(pg, "james"); money_page(pg)
    check(f"before any cost, made this month is $500 ({pg.evaluate(MADE)})", pg.evaluate(MADE) == "$500")
    check("an admin sees 'Add cost' on Profits", pg.is_visible("#costAdd"))
    # add a $30 cost charged to Gio
    pg.click("#costAdd"); pg.wait_for_selector(".ov.on #cxL")
    pg.click(".ov.on [data-ok]"); pg.wait_for_timeout(300)
    check("the form says what's missing instead of saving an empty cost", "Say what the cost was" in pg.inner_text("#cxE"))
    pg.fill("#cxL", "Claude subscription"); pg.fill("#cxA", "30"); pg.select_option("#cxP", ids["gio"]); pg.click(".ov.on [data-ok]")
    pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(1500)
    check("the cost is saved with what, how much and whose money", any(e["label"] == "Claude subscription" and e["amount"] == 30 and e["charged_to"] == ids["gio"] for e in F.t["expenses"]))
    check(f"made this month drops to $470 ({pg.evaluate(MADE)})", pg.evaluate(MADE) == "$470")
    check("Profits explains it: payments minus costs", "$500 in payments" in pg.inner_text("#pg-profits") and "$30 costs" in pg.inner_text("#pg-profits"))
    check("the cost is listed under Company costs", "Claude subscription" in pg.inner_text("#pg-profits .costs"))
    pg.evaluate("async()=>{await go('dash')}"); pg.wait_for_timeout(1800)
    check(f"the Dashboard's 'Made in' box drops to $470 too", pg.inner_text(".mtile .mv").replace(" ", "").replace("\n", "") == "$470")
    pg.evaluate("async()=>{B.data=null;await ensureBoard(true);setP('lbMetric','money');setP('lbPeriod','month');await go('board');drawRanks(true)}"); pg.wait_for_timeout(1800)
    check(f"Gio's leaderboard money drops by the cost ({pg.evaluate(BOARD, ids['gio'])})", pg.evaluate(BOARD, ids["gio"]) == "$470")
    check(f"James's leaderboard money is untouched ({pg.evaluate(BOARD, ids['james'])})", pg.evaluate(BOARD, ids["james"]) == "$0")
    check("the leaderboard explains costs come off", "minus company costs" in pg.inner_text("#lbBody"))
    # a bigger cost charged to James: his total goes below zero and reads -$
    pg.evaluate("async()=>{await go('profits')}"); pg.wait_for_timeout(800)
    pg.click("#costAdd"); pg.wait_for_selector(".ov.on #cxL"); pg.fill("#cxL", "Website hosting"); pg.fill("#cxA", "40.5"); pg.click(".ov.on [data-ok]")
    pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(1200)
    check("by default a cost comes off the admin's own money", any(e["label"] == "Website hosting" and e["charged_to"] == ids["james"] for e in F.t["expenses"]))
    pg.evaluate("async()=>{B.data=null;await ensureBoard(true);await go('board');drawRanks(true)}"); pg.wait_for_timeout(1800)
    check(f"a total below zero reads −$40.50 ({pg.evaluate(BOARD, ids['james'])})", pg.evaluate(BOARD, ids["james"]) == "−$40.50")
    # someone who isn't an admin
    pg.evaluate("api('sign_out')"); signin(pg, "gio"); money_page(pg)
    check(f"Gio sees the same total after costs ({pg.evaluate(MADE)})", pg.evaluate(MADE) == "$429.50")
    check("Gio sees the costs", "Claude subscription" in pg.inner_text("#pg-profits .costs") and "Website hosting" in pg.inner_text("#pg-profits .costs"))
    check("Gio has no 'Add cost' button and no remove buttons", not pg.query_selector("#costAdd") and not pg.query_selector("[data-cdel]"))
    r = pg.evaluate("async()=>await api('sb_rpc','exp_add',{p_label:'x',p_amount:1,p_on:null,p_to:null})")
    check("...and the database refuses him even if he tries directly", not r.get("ok"))
    # remove a cost as admin
    pg.evaluate("api('sign_out')"); signin(pg, "james"); money_page(pg)
    cid = next(e["id"] for e in F.t["expenses"] if e["label"] == "Claude subscription")
    pg.click(f"[data-cdel='{cid}']"); pg.wait_for_selector(".ov.on [data-ok]"); pg.click(".ov.on [data-ok]")
    pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(1500)
    check("an admin removes a cost and the money goes back up", not any(e["label"] == "Claude subscription" for e in F.t["expenses"]) and pg.evaluate(MADE) == "$459.50")
    check("no page errors", not errs or print(errs))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
