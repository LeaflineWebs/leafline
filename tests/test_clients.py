"""12.0: clients. Set clients up from existing deals, see who owes what, open a client's profile (overview, services,
money, activity), confirm a payment from the client, add notes, edit, archive, delete (admins only, deals kept), and the
connections (dashboard card, Profits chips, Pipeline "Won", invoices). Runs the PC app (desktop engine) and the website
build at phone size against the fake shared database (the real database rules are in tests/pg/test_clients_sql.mjs)."""
import os, sys, tempfile, threading, time, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from datetime import date, timedelta
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
T = date.today(); D = lambda n: (T - timedelta(days=n)).isoformat()
MW, MS, OAK, PINE = ("d0000000-0000-4000-8000-0000000000%02d" % i for i in (1, 2, 3, 4))
def deal(i, client, up, mo, months, closed, conf=""):
    F.t["deals"].append(dict(id=i, client=client, upfront=up, monthly=mo, months=months, closed_at=closed, first_bill=closed, notes="", owner_id=ids["gio"],
                             confirmed=conf, version=1, updated_at=F.now(), created_at=F.now()))
deal(MW, "Maple Roofing - Website", 1000, 0, 0, D(20))                      # due 20 days ago, not confirmed: overdue
deal(MS, "Maple Roofing - SEO", 0, 99, 0, D(5))                              # monthly, first one 5 days ago
deal(OAK, "Oak Plumbing", 0, 250, 0, D(25), D(25) + ":monthly")             # monthly, first one confirmed, next one in a few days
F.t["leads"].append(dict(id="L9", name="Pine Spa", phone="(519) 555-0109", owner_name="Lee", email="lee@pinespa.ca", rating="4.5", reviews="9", website="https://pinespa.ca",
                         address="9 Pine St", search="Spa | London", btype="Spa", hours="", status="green", notes="Loves the mockup", enriched=False,
                         added_at=F.now(), called_at=F.now(), meeting_at=None, called_by=ids["gio"], version=1, updated_at=F.now(), created_at=F.now(), phone_key="5195550109"))
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
cl = lambda name: next((c for c in F.t["clients"] if c["name"] == name), None)
links = lambda c: sorted(x["deal_id"] for x in F.t["client_deals"] if c and x["client_id"] == c["id"])
NOSIDE = "()=>document.documentElement.scrollWidth<=innerWidth+1"

def signin(pg, who, base):
    pg.goto(base); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.press("#lgPass", "Enter")
    pg.wait_for_function(f"typeof S!=='undefined'&&S.ready&&S.me&&S.me.username==='{who}'", timeout=60000)
    if "t=tok" in base:
        t0 = time.time()
        while api._sync.status["state"] != "synced" and time.time() - t0 < 20: time.sleep(.2)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    pg.evaluate("async()=>{await reload()}"); pg.wait_for_timeout(500)

def clients(pg):
    pg.evaluate("async()=>{CLI.at=0;await reload();await go('clients',true)}"); pg.wait_for_timeout(1500)

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:400])); pg.on("dialog", lambda d: d.accept())
    DESK = f"http://127.0.0.1:{port}/?t=tok&nointro"

    print("1. finding Clients, and setting them up from the deals you already have (PC app)")
    signin(pg, "gio", DESK)
    grp = pg.evaluate("()=>{const b=document.querySelector('.nv[data-go=clients]');let e=b&&b.previousElementSibling;while(e&&!e.classList.contains('ngrp'))e=e.previousElementSibling;return e&&e.textContent}")
    check(f"the sidebar has Clients under 'Clients & money' ({grp})", grp == "Clients & money")
    check("the sidebar is grouped: Selling, Clients & money, Organize, Team", pg.evaluate("()=>[...document.querySelectorAll('#nav .ngrp')].map(g=>g.textContent).filter(Boolean).join('|')") == "Selling|Clients & money|Organize|Team")
    check("on a computer the floating page bar is gone (the sidebar is the navigation)", not pg.is_visible("#fnav"))
    clients(pg)
    check("with no clients yet, the page offers to set them up from the 3 deals", "No clients yet" in pg.inner_text("#pg-clients") and pg.is_visible("#clGroup2"))
    before = [(d["id"], d["client"], d["upfront"], d["monthly"], d.get("confirmed")) for d in F.t["deals"]]
    pg.click("#clGroup2"); pg.wait_for_selector(".ov.on .cg-list")
    names = pg.evaluate("()=>[...document.querySelectorAll('.ov.on [data-gn]')].map(i=>i.value)")
    check(f"deals with the same business name become one client ({names})", names == ["Maple Roofing", "Oak Plumbing"])
    pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=20000); pg.wait_for_timeout(800)
    check("two clients are created, with their deals as services", links(cl("Maple Roofing")) == sorted([MW, MS]) and links(cl("Oak Plumbing")) == [OAK], [links(cl("Maple Roofing")), links(cl("Oak Plumbing"))])
    check("the deals themselves didn't change", before == [(d["id"], d["client"], d["upfront"], d["monthly"], d.get("confirmed")) for d in F.t["deals"]])
    t = pg.inner_text("#pg-clients")
    check("the summary: 2 active clients, $349 monthly recurring", "Active clients\n2" in t and "$349" in t, t[:300])
    row = lambda n: pg.inner_text(f"#pg-clients .cl-row:not(.hd):has-text('{n}')")
    check("Maple Roofing shows 'Payment overdue' and what it owes ($1,000 + $99)", "Payment overdue" in row("Maple Roofing") and "$1,099" in row("Maple Roofing"), row("Maple Roofing"))
    check("Oak Plumbing is paid up, $250/mo, $250 paid", "Paid up" in row("Oak Plumbing") and "$250" in row("Oak Plumbing"), row("Oak Plumbing"))
    check("no sideways scrolling on the list", pg.evaluate(NOSIDE))

    print("2. search, filters, sorting")
    pg.fill("#clQ", "seo"); pg.wait_for_timeout(500)
    check("searching finds a client by one of its services ('seo' -> Maple)", pg.evaluate("()=>[...document.querySelectorAll('#pg-clients .cl-row:not(.hd) .cl-nm b')].map(b=>b.textContent)") == ["Maple Roofing"])
    check("...and the search box keeps focus while you type", pg.evaluate("()=>document.activeElement.id") == "clQ")
    pg.fill("#clQ", ""); pg.wait_for_timeout(400)
    pg.select_option("#clPay", "overdue"); pg.wait_for_timeout(400)
    check("'Payment overdue' shows only Maple", pg.evaluate("()=>document.querySelectorAll('#pg-clients .cl-row:not(.hd)').length") == 1 and "Maple" in pg.inner_text("#pg-clients .cl-list"))
    pg.select_option("#clPay", "clear"); pg.wait_for_timeout(400)
    check("'Paid up' shows only Oak", pg.evaluate("()=>[...document.querySelectorAll('#pg-clients .cl-row:not(.hd) .cl-nm b')].map(b=>b.textContent)") == ["Oak Plumbing"])
    pg.select_option("#clPay", "all"); pg.select_option("#clSort", "owe"); pg.wait_for_timeout(400)
    check("sorting by 'Most owing' puts Maple first", pg.evaluate("()=>document.querySelector('#pg-clients .cl-row:not(.hd) .cl-nm b').textContent") == "Maple Roofing")
    pg.select_option("#clSort", "name"); pg.wait_for_timeout(300)

    print("3. a client's profile")
    pg.click("#pg-clients .cl-row:has-text('Maple Roofing')"); pg.wait_for_selector(".cp-top")
    t = pg.inner_text("#pg-clients").lower()
    check("the overview: status, money at a glance, team, latest activity", all(x in t for x in ("active", "paid so far", "owing", "team", "gio", "latest")), t[:400])
    check("'Record payment' is offered because a payment is due", pg.is_visible("[data-a=pay]"))
    pg.click("[data-tab=svc]"); pg.wait_for_timeout(600)
    t = pg.inner_text("#pg-clients .cp-body")
    check("Services lists both deals with their prices", "Maple Roofing - Website" in t and "$1,000 upfront" in t and "$99/month" in t, t[:300])
    pg.click("[data-tab=money]"); pg.wait_for_timeout(600)
    t = pg.inner_text("#pg-clients .cp-body").lower()
    check("Money: agreed price, total revenue, outstanding, and the payments waiting", "agreed price" in t and "$1,099" in t and "waiting for confirmation" in t and "overdue" in t, t[:400])
    pg.click("#pg-clients .cp-r:has-text('Maple Roofing - Website') [data-pay$='|1']"); pg.wait_for_selector(".ov.on .spl-row")
    check("confirming opens the same 'who gets credit' pop-up as Profits", pg.is_visible(".ov.on [data-splok]"))
    pg.click(".ov.on [data-splok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    key = D(20) + ":upfront"; t0 = time.time()
    while key not in (next(d for d in F.t["deals"] if d["id"] == MW).get("confirmed") or "") and time.time() - t0 < 25: api.sync_retry(); time.sleep(.5)
    check("the payment is confirmed on the deal (one record, shared with Profits)", key in next(d for d in F.t["deals"] if d["id"] == MW)["confirmed"])
    pg.wait_for_timeout(1500); pg.evaluate("async()=>{await reload()}"); pg.wait_for_timeout(1200)
    t = pg.inner_text("#pg-clients .cp-body").lower()
    check("...and the client's money updates: $1,000 revenue, $99 still owing", "$1,000" in t and "payment history" in t and "$99" in t, t[:500])
    pg.click("[data-tab=act]"); pg.wait_for_timeout(600)
    pg.select_option("#cpKind", "call"); pg.fill("#cpBody", "Called Sam, wants a landing page in March"); pg.click("#cpAdd"); pg.wait_for_timeout(1200)
    ev = [e for e in F.t["client_events"] if e["client_id"] == cl("Maple Roofing")["id"]]
    check("adding a call to the timeline saves it for the team", any(e["kind"] == "call" and "landing page" in e["body"] for e in ev))
    t = pg.inner_text("#pg-clients .cp-body")
    check("the timeline also shows the payment received and the services added", "Payment received: $1,000" in t and "Service added" in t and "landing page" in t, t[:600])

    print("4. editing, archiving, deleting")
    pg.click("[data-a=edit]"); pg.wait_for_selector(".ov.on #ceName")
    pg.fill("#ceEm", "sam@maple"); pg.click(".ov.on [data-ok]"); pg.wait_for_timeout(400)
    check("a bad email is caught before saving", "doesn't look right" in pg.inner_text(".ov.on #ceErr"))
    pg.fill("#ceEm", "sam@mapleroofing.ca"); pg.fill("#ceCt", "Sam Lee"); pg.fill("#ceTags", "Website, SEO"); pg.select_option("#cePr", "high")
    pg.check(f".ov.on [data-tm='{ids['tim']}']"); pg.fill(f".ov.on [data-tr='{ids['tim']}']", "Design")
    pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(1200)
    c = cl("Maple Roofing")
    check("contact, tags, priority and team (with responsibilities) are saved", c["email"] == "sam@mapleroofing.ca" and c["tags"] == ["SEO", "Website"] and c["priority"] == "high" and {"id": ids["tim"], "role": "Design"} in c["team"], c)
    check("the profile shows High priority and the tags", "High priority" in pg.inner_text(".cp-top") and "#SEO" in pg.inner_text(".cp-top"))
    pg.click("[data-a=more]"); pg.wait_for_timeout(200)
    check("Gio (not an admin) can archive but has no Delete", pg.is_visible(".cp-menu [data-a=arch]") and not pg.query_selector(".cp-menu [data-a=del]"))
    pg.click(".cp-menu [data-a=arch]"); pg.wait_for_timeout(1500)
    check("archiving keeps the client, marked archived", cl("Maple Roofing")["archived_at"] and "Archived" in pg.inner_text(".cp-top"))
    pg.click("#cpBack"); pg.wait_for_timeout(1000)
    check("archived clients drop out of the current list", "Maple Roofing" not in pg.inner_text("#pg-clients .cl-list"))
    pg.select_option("#clSt", "archived"); pg.wait_for_timeout(400)
    check("...and show under 'Archived'", "Maple Roofing" in pg.inner_text("#pg-clients .cl-list"))
    pg.click("#pg-clients .cl-row:has-text('Maple Roofing')"); pg.wait_for_selector(".cp-top"); pg.click("[data-a=more]"); pg.click(".cp-menu [data-a=unarch]"); pg.wait_for_timeout(1500)
    check("Reactivate brings it back", not cl("Maple Roofing")["archived_at"])
    pg.evaluate("()=>{CLI.f.st='current';cliBack()}"); pg.wait_for_timeout(600)

    print("5. connections: dashboard, Profits, Pipeline, invoices, sidebar")
    pg.evaluate("async()=>{await go('dash',true)}"); pg.wait_for_timeout(2500)
    t = (pg.inner_text("#clDash") if pg.query_selector("#clDash") else "").lower()
    check("the dashboard has a Clients card: active, monthly, outstanding", "active clients" in t and "monthly recurring" in t and "outstanding" in t, t[:300])
    pg.evaluate("async()=>{await go('profits',true)}"); pg.wait_for_timeout(2000)
    chips = pg.evaluate("()=>[...document.querySelectorAll('#pg-profits .cl-link')].map(c=>c.textContent)")
    check(f"on Profits each deal shows its client ({chips})", sorted(chips) == ["Maple Roofing", "Maple Roofing", "Oak Plumbing"])
    pg.click("#pg-profits .cl-link:has-text('Oak Plumbing')"); pg.wait_for_selector(".cp-top"); pg.wait_for_timeout(500)
    check("...and clicking it opens that client's Money tab", "Oak Plumbing" in pg.inner_text(".cp-top") and pg.evaluate("()=>CLI.tab") == "money")
    pg.click(".nv[data-go=clients]"); pg.wait_for_timeout(1200)
    check("clicking Clients in the sidebar goes back to the list", pg.query_selector("#pg-clients .cl-list") is not None and pg.query_selector(".cp-top") is None)
    pg.evaluate("async()=>{await go('pipeline',true)}"); pg.wait_for_timeout(1500)
    pg.evaluate("async()=>{await plMove('L9','won')}"); pg.wait_for_timeout(1200)
    check("moving a business to Won in the Pipeline offers to add it as a client", "Add them as a client" in pg.inner_text("#toast"), pg.inner_text("#toast"))
    pg.evaluate("()=>cliFromLead(S.called.find(l=>l.id==='L9'))"); pg.wait_for_selector(".ov.on #ceName")
    check("...prefilled from the lead: name, contact, phone, email, website", pg.input_value("#ceName") == "Pine Spa" and pg.input_value("#ceCt") == "Lee" and pg.input_value("#cePh") == "(519) 555-0109" and pg.input_value("#ceEm") == "lee@pinespa.ca")
    pg.click(".ov.on [data-ok]"); pg.wait_for_selector(".cp-top", timeout=15000); pg.wait_for_timeout(800)
    check("the new client is linked to its lead and opens on Services", cl("Pine Spa") and cl("Pine Spa")["lead_id"] == "L9" and pg.evaluate("()=>CLI.tab") == "svc")
    check("invoices from a deal now point at the deal (shared id)", pg.evaluate("()=>{let got=null;const o=invStart;invStart=x=>{got=x};invFromDeal(S.deals.find(d=>d.client==='Oak Plumbing'));return new Promise(r=>setTimeout(()=>{invStart=o;r(got&&got.deal_id)},1500))}") == OAK)
    check("no page errors (PC)", not errs, errs[:3])

    print("6. admins delete (the deals stay), and before the 19th update")
    pg2 = br.new_page(viewport={"width": 1280, "height": 800}); errs2 = []; pg2.on("pageerror", lambda e: errs2.append(str(e))); pg2.on("dialog", lambda d: d.accept())
    import build_web
    site = tempfile.mkdtemp(); build_web.build(site)
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(s, *a): pass
    ws = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); threading.Thread(target=ws.serve_forever, daemon=True).start()
    WEB = f"http://127.0.0.1:{ws.server_address[1]}/?nointro"
    signin(pg2, "james", WEB); clients(pg2)
    check("the website shows the same clients", all(n in pg2.inner_text("#pg-clients .cl-list") for n in ("Maple Roofing", "Oak Plumbing", "Pine Spa")))
    pg2.click("#pg-clients .cl-row:has-text('Oak Plumbing')"); pg2.wait_for_selector(".cp-top"); pg2.click("[data-a=more]")
    check("an admin sees Delete", pg2.is_visible(".cp-menu [data-a=del]"))
    pg2.click(".cp-menu [data-a=del]"); pg2.wait_for_selector(".ov.on #cdOk")
    check("Delete explains the deals and payments are kept, and needs a tick first", "are kept" in pg2.inner_text(".ov.on") and pg2.is_disabled(".ov.on [data-del]"))
    pg2.check("#cdOk"); pg2.click(".ov.on [data-del]"); pg2.wait_for_timeout(1500)
    check("the client is deleted, its deal is still there", cl("Oak Plumbing") is None and any(d["id"] == OAK for d in F.t["deals"]))
    F.clients_cap = False; clients(pg2)
    check("before the 19th database update the page says what to run", "19th database update" in pg2.inner_text("#pg-clients"))
    F.clients_cap = True
    check("no page errors (website)", not errs2, errs2[:3])

    print("7. phones")
    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); ph = ctx.new_page(); errs3 = []; ph.on("pageerror", lambda e: errs3.append(str(e)))
    signin(ph, "tim", WEB); clients(ph)
    check("phone: the list fits (no sideways scrolling)", ph.evaluate(NOSIDE))
    check("phone: each client is a card with Pays / Paid / Owing labels", ph.is_visible("#pg-clients .cl-row:not(.hd) .c-owe .lbl") and not ph.is_visible("#pg-clients .cl-row.hd"))
    ph.evaluate("()=>openSheet()"); ph.wait_for_timeout(600)
    check("phone: the More menu is grouped like the sidebar, with Clients", "clients & money" in ph.inner_text("#sheetGrid").lower() and ph.is_visible("#sheetGrid [data-go=clients]"))
    ph.click("#sheetGrid [data-go=clients]"); ph.wait_for_timeout(1200)
    ph.click("#pg-clients .cl-row:has-text('Maple Roofing')"); ph.wait_for_selector(".cp-top")
    for tb in ("over", "svc", "money", "act"):
        ph.click(f"[data-tab={tb}]"); ph.wait_for_timeout(500)
        if not ph.evaluate(NOSIDE): check(f"phone: the {tb} tab fits", False); break
    else: check("phone: every profile tab fits the screen", True)
    check("phone: the action buttons and tabs fit on screen", ph.evaluate("()=>[...document.querySelectorAll('.cp-acts .btn,.cp-tabs button')].every(b=>{const r=b.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1})"))
    check("no page errors (phone)", not errs3, errs3[:3])
    br.close()
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
