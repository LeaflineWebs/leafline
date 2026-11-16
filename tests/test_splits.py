"""11.18: profit splits. When a payment is confirmed, its money can be split between teammates by percent (Omar 60%,
Jay 40%). Saved for that payment and as the deal's default; the leaderboard, Revenue Champion and Deal Closer count each
person's share. Only an admin or the person the deal is credited to can split it. Runs the PC app (desktop engine) AND
the website build against the fake shared database (the real database rules are in tests/pg/test_splits_sql.mjs)."""
import os, sys, tempfile, threading, time, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from datetime import date
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("omar", "jay", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
TODAY = date.today().isoformat()
MAPLE, OAK = "d0000000-0000-4000-8000-0000000000c1", "d0000000-0000-4000-8000-0000000000c2"
F.t["deals"].append(dict(id=MAPLE, client="Maple Roofing", upfront=1000, monthly=0, months=0, closed_at=TODAY, first_bill=TODAY, notes="",
                         owner_id=ids["omar"], confirmed="", version=1, updated_at=F.now(), created_at=F.now()))
F.t["deals"].append(dict(id=OAK, client="Oak Plumbing", upfront=500, monthly=0, months=0, closed_at=TODAY, first_bill=TODAY, notes="",
                         owner_id=ids["tim"], confirmed="", version=1, updated_at=F.now(), created_at=F.now()))
import leafline_backend as B
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c, extra=None):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l, "" if extra is None else extra)

api = B.Api(); api._ready.set()
srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
BOARD = "(id)=>{const e=document.querySelector(`#lbBody [data-lbid=\"${id}\"] .v`);return e&&e.innerText.replace(/\\s/g,'')}"
key = TODAY + ":upfront"
def splits(deal, k): r = next((x for x in F.t["deal_splits"] if x["deal_id"] == deal and x["pay_key"] == k), None); return r and [(s["id"], s["pct"]) for s in r["shares"]]

def signin(pg, who, base):
    pg.goto(base); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.press("#lgPass", "Enter")
    pg.wait_for_function(f"typeof S!=='undefined'&&S.ready&&S.me&&S.me.username==='{who}'", timeout=60000)
    if "t=tok" in base:
        t0 = time.time()
        while api._sync.status["state"] != "synced" and time.time() - t0 < 20: time.sleep(.2)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    pg.evaluate("async()=>{await reload()}"); pg.wait_for_timeout(500)

def profits(pg):
    pg.evaluate("async()=>{B.data=null;await ensureBoard(true);await reload();await go('profits',true)}"); pg.wait_for_timeout(1500)

def board_money(pg):
    pg.evaluate("async()=>{B.data=null;await ensureBoard(true);setP('lbMetric','money');setP('lbPeriod','all');await go('board',true);drawRanks(true)}"); pg.wait_for_timeout(1800)
    return {n: pg.evaluate(BOARD, ids[n]) for n in ("omar", "jay", "tim", "james")}

def confirm_btn(pg, deal_client):
    return pg.evaluate("""(c)=>{const row=[...document.querySelectorAll('#pg-profits .tocf .prow, #pg-profits .types .prow')].find(r=>r.innerText.includes(c)&&r.querySelector('[data-pay$="|1"]'));
        if(!row)return null;const b=row.querySelector('[data-pay$="|1"]');b.setAttribute('data-test','go');return true}""", deal_client)

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:600]))
    DESK = f"http://127.0.0.1:{port}/?t=tok&nointro"

    print("1. Omar confirms his payment and splits it 60/40 with Jay (PC app)")
    signin(pg, "omar", DESK); profits(pg)
    check("each deal knows its shared-database id", pg.evaluate("()=>S.deals.every(d=>/^[0-9a-f-]{36}$/.test(d.rid||''))"), pg.evaluate("()=>S.deals.map(d=>d.rid)"))
    check("Maple Roofing is waiting to be confirmed", confirm_btn(pg, "Maple Roofing"))
    pg.click("[data-test=go]"); pg.wait_for_selector(".ov.on .spl-row")
    check("pressing Confirm opens the pop-up with 'Who gets credit', starting as Omar 100%",
          pg.evaluate("()=>{const r=[...document.querySelectorAll('.ov.on .spl-row')];return r.length===1&&r[0].querySelector('select').value===S.me.id&&r[0].querySelector('[data-pct]').value==='100'}"))
    check("it shows the payment: client, date, type and amount", all(t in pg.inner_text(".ov.on .spl-head") for t in ("Maple Roofing", "Upfront", "$1,000")))
    pg.click(".ov.on [data-add]"); pg.wait_for_timeout(200)
    pg.select_option(".ov.on .spl-row:nth-child(2) select", ids["jay"])
    pg.fill(".ov.on .spl-row:nth-child(1) [data-pct]", "70"); pg.fill(".ov.on .spl-row:nth-child(2) [data-pct]", "40")
    check("the total warns when it isn't 100%", "110% of 100%" in pg.inner_text(".ov.on .spl-sum"))
    pg.click(".ov.on [data-splok]"); pg.wait_for_timeout(500)
    check("...and Confirm refuses to save it", "add up to 110%" in pg.inner_text(".ov.on #splErr") and splits(MAPLE, key) is None and key not in (F.t["deals"][0].get("confirmed") or ""))
    pg.fill(".ov.on .spl-row:nth-child(1) [data-pct]", "60")
    check("each line shows its share of the money as you type", pg.inner_text(".ov.on .spl-row:nth-child(1) .spl-amt") == "$600" and pg.inner_text(".ov.on .spl-row:nth-child(2) .spl-amt") == "$400")
    check("the total turns green at 100%", "100%" in pg.inner_text(".ov.on .spl-sum") and "ok" in pg.get_attribute(".ov.on .spl-sum", "class"))
    pg.screenshot(path=os.path.join(os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp(), "split_confirm.png"))
    pg.click(".ov.on [data-splok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    t0 = time.time()
    while key not in (F.t["deals"][0].get("confirmed") or "") and time.time() - t0 < 20: api.sync_retry(); time.sleep(.5)
    check("the payment is confirmed (and uploads like before)", key in F.t["deals"][0]["confirmed"])
    check("the split is saved for that payment: Omar 60%, Jay 40%", splits(MAPLE, key) == [(ids["omar"], 60), (ids["jay"], 40)], splits(MAPLE, key))
    check("...and as the deal's default for later payments", splits(MAPLE, "") == [(ids["omar"], 60), (ids["jay"], 40)])
    check("the team sees it in Activity (percents, no money)", any(a["summary"] == "Omar split Maple Roofing: Omar 60%, Jay 40%" for a in F.t["activity"]))
    m = board_money(pg)
    check(f"leaderboard money: Omar $600 and Jay $400 ({m})", m["omar"] == "$600" and m["jay"] == "$400")
    check("Jay gets the Deal Closer badge for his share of a new deal", "closer" in pg.evaluate("(i)=>B.badges[i]||[]", ids["jay"]))
    check("Revenue Champion goes to Omar (most money in 30 days, after the split)", "revenue" in pg.evaluate("(i)=>B.badges[i]||[]", ids["omar"]) and "revenue" not in pg.evaluate("(i)=>B.badges[i]||[]", ids["jay"]))
    profits(pg)
    chip = pg.evaluate("()=>{const c=document.querySelector('#pg-profits .spl-chip');return c&&c.innerText}")
    check(f"the confirmed payment shows its split on Profits ({chip})", chip and "Omar 60%" in chip and "Jay 40%" in chip)
    pg.evaluate("()=>document.querySelector('#pg-profits .types').scrollIntoView({block:'center'})"); pg.wait_for_timeout(500); pg.screenshot(path=os.path.join(os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp(), "split_profits.png"))

    print("2. Changing the split later, from the chip")
    pg.click("#pg-profits .spl-chip"); pg.wait_for_selector(".ov.on .spl-row")
    pg.click(".ov.on [data-even]"); pg.wait_for_timeout(200)
    check("Split evenly makes it 50/50", [pg.input_value(f".ov.on .spl-row:nth-child({i}) [data-pct]") for i in (1, 2)] == ["50", "50"])
    pg.click(".ov.on [data-splok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(600)
    check("the new split replaces the old one", splits(MAPLE, key) == [(ids["omar"], 50), (ids["jay"], 50)] and sum(1 for x in F.t["deal_splits"] if x["deal_id"] == MAPLE and x["pay_key"] == key) == 1)
    m = board_money(pg); check(f"leaderboard follows: Omar $500, Jay $500 ({m})", m["omar"] == "$500" and m["jay"] == "$500")

    print("3. Omar can't split Tim's deal; he can still confirm it")
    profits(pg)
    check("Oak Plumbing (Tim's) is waiting", confirm_btn(pg, "Oak Plumbing"))
    pg.click("[data-test=go]"); pg.wait_for_selector(".ov.on .spl-sec")
    check("the pop-up explains only an admin or Tim can change who gets credit, and shows Tim 100%",
          "Only an admin or Tim" in pg.inner_text(".ov.on .spl-sec") and not pg.query_selector(".ov.on .spl-row") and "Tim" in pg.inner_text(".ov.on .spl-ro"))
    pg.click(".ov.on [data-splok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    t0 = time.time()
    while key not in (F.t["deals"][1].get("confirmed") or "") and time.time() - t0 < 20: api.sync_retry(); time.sleep(.5)
    check("...and confirming it works", key in F.t["deals"][1]["confirmed"] and splits(OAK, key) is None)
    r = pg.evaluate("(d)=>api('sb_rpc','deal_split_set',{p_deal:d,p_key:'',p_shares:[{id:S.me.id,pct:100}],p_default:true})", OAK)
    check("...and the database refuses him even if he tries directly", not r.get("ok") and "Only an admin" in (r.get("error") or ""), r)
    m = board_money(pg); check(f"Tim gets all of Oak Plumbing ($500) ({m})", m["tim"] == "$500")

    print("4. An admin splits a deal from the deal pop-up (PC app)")
    pg.evaluate("api('sign_out')"); signin(pg, "james", DESK); profits(pg)
    pg.evaluate("()=>{const d=S.deals.find(x=>x.client==='Oak Plumbing');dealModal(d)}"); pg.wait_for_selector(".ov.on #dSplit .spl-chip", timeout=15000)
    check("the deal pop-up shows its profit split (Tim)", pg.inner_text(".ov.on #dSplit").strip() == "Tim")
    pg.click(".ov.on #dSplit .spl-chip"); pg.wait_for_selector(".ov.on .spl-row")
    pg.click(".ov.on [data-add]"); pg.wait_for_timeout(200)
    pg.select_option(".ov.on .spl-row:nth-child(2) select", ids["james"]); pg.fill(".ov.on .spl-row:nth-child(1) [data-pct]", "75"); pg.fill(".ov.on .spl-row:nth-child(2) [data-pct]", "25")
    pg.click(".ov.on [data-splok]"); pg.wait_for_timeout(1500)
    check("the admin's split is saved as the deal's default", splits(OAK, "") == [(ids["tim"], 75), (ids["james"], 25)], splits(OAK, ""))
    m = board_money(pg); check(f"the already-confirmed payment follows the deal's split: Tim $375, James $125 ({m})", m["tim"] == "$375" and m["james"] == "$125")

    print("5. Same thing on the website, phone size")
    import build_web
    site = tempfile.mkdtemp(); build_web.build(site)
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(s, *a): pass
    wsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); wport = wsrv.server_address[1]
    threading.Thread(target=wsrv.serve_forever, daemon=True).start()
    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); wp = ctx.new_page(); wp.on("pageerror", lambda e: errs.append(str(e)))
    signin(wp, "omar", f"http://127.0.0.1:{wport}/?nointro"); profits(wp)
    chip = wp.evaluate("()=>{const c=document.querySelector('#pg-profits .spl-chip');return c&&c.innerText}")
    check(f"the website shows the same split ({chip})", chip and "Omar 50%" in chip and "Jay 50%" in chip)
    wp.click("#pg-profits .spl-chip"); wp.wait_for_selector(".ov.on .spl-row")
    check("the split pop-up fits a phone screen", wp.evaluate("()=>{const d=document.querySelector('.ov.on .dlg').getBoundingClientRect();return d.left>=0&&d.right<=innerWidth+.5&&document.documentElement.scrollWidth<=innerWidth}"))
    wp.wait_for_timeout(900); wp.screenshot(path=os.path.join(os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp(), "split_phone.png"))
    check("on a phone the pop-up sits above the bottom bar", wp.evaluate("()=>{const r=document.querySelector('.ov.on [data-splok]').getBoundingClientRect(),e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!(e&&e.closest('.ov'))}"))
    wp.fill(".ov.on .spl-row:nth-child(1) [data-pct]", "80"); wp.fill(".ov.on .spl-row:nth-child(2) [data-pct]", "20")
    wp.click(".ov.on [data-splok]"); wp.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); wp.wait_for_timeout(600)
    check("saving from the website works too (80/20)", splits(MAPLE, key) == [(ids["omar"], 80), (ids["jay"], 20)])
    m = board_money(wp); check(f"website leaderboard: Omar $800, Jay $200 ({m})", m["omar"] == "$800" and m["jay"] == "$200")
    ctx.close()

    print("6. Before the 16th database update")
    F.split_cap = False
    ctx = br.new_context(viewport={"width": 1440, "height": 900}); wp = ctx.new_page(); wp.on("pageerror", lambda e: errs.append(str(e)))
    F.t["deals"].append(dict(id="d0000000-0000-4000-8000-0000000000c3", client="Birch Dental", upfront=300, monthly=0, months=0, closed_at=TODAY, first_bill=TODAY, notes="",
                             owner_id=ids["omar"], confirmed="", version=1, updated_at=F.now(), created_at=F.now()))
    signin(wp, "omar", f"http://127.0.0.1:{wport}/?nointro"); profits(wp)
    check("Birch Dental is waiting", confirm_btn(wp, "Birch Dental"))
    wp.click("[data-test=go]"); wp.wait_for_selector(".ov.on .spl-sec")
    check("the pop-up says splitting needs the 16th database update", "16th database update" in wp.inner_text(".ov.on .spl-sec"))
    wp.click(".ov.on [data-splok]"); wp.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    t0 = time.time()
    while key not in (F.t["deals"][2].get("confirmed") or "") and time.time() - t0 < 20: time.sleep(.5)
    check("...and confirming still works", key in F.t["deals"][2]["confirmed"])
    m = board_money(wp); check(f"without splits, money counts 100% for the deal's owner (Omar ${300} on top of his share before) ({m})", m["omar"] == "$1,300" and m["jay"] == "$0")
    ctx.close(); F.split_cap = True

    check("no page errors", not errs, errs[:3])
    api._sync.stop.set(); br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
