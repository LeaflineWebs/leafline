"""11.15: invoices (list, filters, editor, templates, settings, payments, PDF), team profile cards, and Kyle + Mubaraq.
Runs the real WEBSITE build (PC and phone sizes) and the PC app's engine against the fake shared database, with the
invoice and team-card functions running on a REAL Postgres with the real migrations (tests/pg/server.mjs)."""
import os, sys, re, tempfile, threading, http.server, functools, time
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
import msg_harness
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james", "kyle", "mubaraq")}
for p in F.t["profiles"]: p["must_change_password"] = False
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
YEAR = time.strftime("%Y")
def page(br, who, phone=False):
    o = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=UA) if phone else dict(viewport={"width": 1440, "height": 900})
    ctx = br.new_context(accept_downloads=True, **o); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    return ctx, pg, errs
def open_invoices(pg):
    pg.evaluate("async()=>{INV.view='list';INV.cur=null;INV.E=null;await go('invoices',true)}")
    pg.wait_for_selector("#pg-invoices .iv-list, #pg-invoices .iv-empty", timeout=20000); pg.wait_for_timeout(300)
def no_overflow(pg): return pg.evaluate("()=>{const p=document.querySelector('.page.on');return p.scrollWidth<=p.clientWidth+1&&document.documentElement.scrollWidth<=innerWidth+1}")
def fill_item(pg, k, d, q, price, tax=True):
    it = f"#ivItems .iv-it[data-k='{k}']"
    pg.fill(f"{it} [data-f=description]", d); pg.fill(f"{it} [data-f=qty]", str(q)); pg.fill(f"{it} [data-f=unit_price]", str(price))
    if not tax: pg.uncheck(f"{it} [data-f=taxable]")
def totals(pg): return pg.inner_text("#ivTot").replace("\n", " ")
def pdf_of(pg):
    with pg.expect_download(timeout=20000) as d: pg.click("[data-a=pdf]")
    return open(d.value.path(), "rb").read(), d.value.suggested_filename

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    print("1. an admin sets up invoices (PC size)")
    ctx, pg, errs = page(br, "james")
    check("Invoices is in the sidebar", pg.is_visible("#nav [data-go=invoices]"))
    open_invoices(pg)
    check("an empty list says how to start", "No invoices yet" in pg.inner_text("#pg-invoices"))
    check("it warns that no e-Transfer email is set yet", "No e-Transfer email is set" in pg.inner_text("#pg-invoices .iv-warn"))
    pg.click("#pg-invoices [data-set]"); pg.wait_for_selector(".ov.on #is_etransfer_email")
    pg.fill("#is_etransfer_email", "pay@leaflineweb.com"); pg.fill("#is_etransfer_name", "Leafline Web Services"); pg.fill("#is_tax_rate", "13"); pg.fill("#is_tax_number", "123456789 RT0001")
    pg.fill("#is_company_website", "leaflineweb.com"); pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(500)
    st = pg.evaluate("()=>INV.settings")
    check("the settings are saved in the database", st["etransfer_email"] == "pay@leaflineweb.com" and float(st["tax_rate"]) == 13 and st["tax_number"] == "123456789 RT0001")
    check("the warning goes away", not pg.query_selector("#pg-invoices .iv-warn"))

    print("2. templates (admin)")
    pg.click("#pg-invoices [data-tpl]"); pg.wait_for_selector(".ov.on .iv-tl")
    check("no templates yet, and it explains what they are", "No templates yet" in pg.inner_text(".ov.on"))
    pg.click(".ov.on [data-new]"); pg.wait_for_selector(".ov.on #it_name")
    pg.fill("#it_name", "Website development"); pg.fill("#it_category", "Websites"); pg.fill("#it_due_days", "7")
    pg.fill(".ov.on #itItems .iv-it[data-k='0'] [data-f=description]", "Website design"); pg.fill(".ov.on #itItems .iv-it[data-k='0'] [data-f=unit_price]", "1200")
    pg.click(".ov.on [data-additem]"); pg.fill(".ov.on #itItems .iv-it[data-k='1'] [data-f=description]", "Hosting (monthly)")
    pg.fill(".ov.on #itItems .iv-it[data-k='1'] [data-f=qty]", "12"); pg.fill(".ov.on #itItems .iv-it[data-k='1'] [data-f=unit_price]", "25.50")
    pg.fill("#it_payment_terms", "50% deposit to start, the rest at launch."); pg.fill("#it_terms", "1. Scope: the pages listed above.\n2. Ownership: yours once paid in full.")
    pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(600)
    tp = pg.evaluate("()=>INV.tpls")
    check("the template is saved with its items and terms", len(tp) == 1 and len(tp[0]["items"]) == 2 and tp[0]["due_days"] == 7 and "Ownership" in tp[0]["terms"])

    print("3. making an invoice")
    pg.click("#pg-invoices [data-new]"); pg.wait_for_selector("#ivCn")
    check("the editor offers the template", pg.is_visible("[data-tplpick]:not([data-tplpick=''])"))
    pg.click(f"[data-tplpick='{tp[0]['id']}']"); pg.wait_for_timeout(400)
    check("picking it fills the items, payment terms and terms", pg.input_value("#ivItems .iv-it[data-k='1'] [data-f=description]") == "Hosting (monthly)" and "deposit" in pg.input_value("#ivPt") and "Ownership" in pg.input_value("#ivTe"))
    pg.fill("#ivCn", "Maple Roofing"); pg.fill("#ivCc", "Sam Lee"); pg.fill("#ivCe", "sam@maple.ca"); pg.fill("#ivCa", "1 King St\nLondon ON")
    pg.click("[data-additem]"); fill_item(pg, 2, "Domain transfer", 1, 20, tax=False)
    pg.select_option("#ivDk", "percent"); pg.fill("#ivDv", "10"); pg.wait_for_timeout(200)
    t = totals(pg)
    # 1200 + 306 + 20 = 1526; 10% = 152.60; taxable 1506 - 150.60 = 1355.40; 13% = 176.20; total 1549.60
    check(f"the totals update as you type ({t})", "$1,526.00" in t and "$152.60" in t and "$176.20" in t and "$1,549.60" in t)
    pg.click("[data-save=sent]"); pg.wait_for_selector(".iv-hero", timeout=15000)
    cur = pg.evaluate("()=>INV.cur")
    check(f"saved and issued with the next number ({cur['number']})", cur["number"] == f"LF-{YEAR}-0001" and cur["status"] == "sent")
    check("the database worked out the same total", float(cur["total"]) == 1549.6 and float(cur["tax_total"]) == 176.2 and float(cur["discount_total"]) == 152.6)
    check("the invoice remembers its template", cur["template_name"] == "Website development")
    check("the e-Transfer email and copy buttons are shown", "pay@leaflineweb.com" in pg.inner_text(".iv-pay") and pg.is_visible("[data-a=copyem]"))
    check("the untaxed item says so", "No HST on this item" in pg.inner_text(".iv-tbl"))

    print("4. the PDF")
    pdf, name = pdf_of(pg)
    check(f"Download PDF gives a real PDF ({name}, {len(pdf)} bytes)", pdf[:5] == b"%PDF-" and pdf.rstrip().endswith(b"%%EOF") and name.startswith(f"LF-{YEAR}-0001"))
    check("it's real text, not a picture (number, client, totals, terms)", all(x in pdf for x in [b"(INVOICE)", b"(Maple Roofing)", b"($1,549.60 CAD)", b"Ownership: yours once paid in full."]) and b"/Image" not in pdf)
    check("the e-Transfer email is a clickable mailto link with the invoice number", b"/URI (mailto:pay@leaflineweb.com)" in pdf and re.search(rb"/URI \(mailto:pay@leaflineweb.com\?subject=Invoice%20LF-\d{4}-0001", pdf) is not None)
    check("the xref table points at every object", (lambda m: m is not None and pdf[int(m.group(1)):int(m.group(1)) + 4] == b"xref")(re.search(rb"startxref\n(\d+)", pdf)))

    print("5. editing, duplicating, paying")
    pg.click("[data-a=edit]"); pg.wait_for_selector("#ivCn"); pg.fill("#ivNo", "Thanks for choosing Leafline!"); pg.click("[data-save=sent]"); pg.wait_for_selector(".iv-hero", timeout=15000)
    check("editing keeps the number and saves the change", pg.evaluate("()=>INV.cur.notes") == "Thanks for choosing Leafline!" and pg.evaluate("()=>INV.cur.number") == f"LF-{YEAR}-0001")
    pg.click("[data-a=dup]"); pg.wait_for_selector("#ivCn", timeout=15000)
    check("Duplicate opens a new draft copy with the next number", pg.evaluate("()=>INV.E.number") == f"LF-{YEAR}-0002" and pg.input_value("#ivCn") == "Maple Roofing")
    pg.fill("#ivCn", "Oak Plumbing"); pg.fill("#ivCe", ""); pg.click("[data-save=draft]"); pg.wait_for_selector(".iv-hero", timeout=15000)
    check("saved as a draft", pg.evaluate("()=>INV.cur.status") == "draft")
    pg.click("[data-back]"); pg.wait_for_selector("#pg-invoices .iv-list"); pg.click(f"#pg-invoices [data-iv]:has-text('LF-{YEAR}-0001')"); pg.wait_for_selector(".iv-hero")
    pg.click("[data-a=pay]"); pg.wait_for_selector(".ov.on #ipA")
    check("Mark paid starts with the full amount and e-Transfer", pg.input_value("#ipA") == "1549.60" and pg.input_value("#ipM") == "e-Transfer")
    pg.fill("#ipR", "CA123456"); pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(600)
    cur = pg.evaluate("()=>INV.cur")
    check("it's marked paid with the payment details and who did it", cur["status"] == "paid" and cur["paid_ref"] == "CA123456" and cur["paid_by_name"] == "James")
    check("a paid invoice can't be edited any more", not pg.query_selector("[data-a=edit]") and pg.is_visible("[data-a=unpay]"))
    pdf, _ = pdf_of(pg)
    check("the PDF of a paid invoice says PAID and shows the balance", b"(PAID)" in pdf and b"(Balance due)" in pdf)

    print("6. a third invoice, voiding, and the list")
    pg.click("[data-back]"); pg.wait_for_selector("#pg-invoices .iv-list"); pg.click("#pg-invoices [data-new]"); pg.wait_for_selector("#ivCn")
    pg.fill("#ivCn", "Cedar Dental"); fill_item(pg, 0, "Logo design", 1, 300); pg.fill("#ivId", "2026-01-05"); pg.fill("#ivDd", "2026-01-20")
    pg.click("[data-save=sent]"); pg.wait_for_selector(".iv-hero", timeout=15000)
    check("an issued invoice past its due date shows as Overdue", pg.evaluate("()=>INV.cur.overdue") is True and "Overdue" in pg.inner_text(".iv-top"))
    pg.click("[data-back]"); pg.wait_for_selector("#pg-invoices .iv-list"); pg.wait_for_timeout(400)
    tabs = pg.evaluate("()=>Object.fromEntries([...document.querySelectorAll('#pg-invoices [data-tab]')].map(b=>[b.dataset.tab,+b.querySelector('b').textContent]))")
    check(f"tab counts: all, drafts, unpaid, overdue, paid ({tabs})", tabs == {"all": 3, "draft": 1, "unpaid": 1, "overdue": 1, "paid": 1, "void": 0})
    stat = pg.inner_text("#pg-invoices .stats")
    check(f"the totals show invoiced, outstanding, overdue and paid ({stat!r})", "$1,888.60" in stat and "$339.00" in stat and "$1,549.60" in stat)   # the $300 logo gets 13% HST: $339
    pg.click("#pg-invoices [data-tab=overdue]"); pg.wait_for_timeout(200)
    rows = lambda: pg.evaluate("()=>[...document.querySelectorAll('#pg-invoices [data-iv]')].map(r=>r.querySelector('.iv-cl b').textContent)")
    check("the Overdue tab shows only the overdue one", rows() == ["Cedar Dental"])
    pg.click("#pg-invoices [data-tab=all]"); pg.fill("#ivQ", "oak"); pg.wait_for_timeout(500)
    check("search by client", rows() == ["Oak Plumbing"])
    pg.fill("#ivQ", ""); pg.wait_for_timeout(500); pg.select_option("#ivC", "Maple Roofing"); pg.wait_for_timeout(200)
    check("filter by client", rows() == ["Maple Roofing"])
    pg.click("#pg-invoices [data-clr]"); pg.wait_for_timeout(200); pg.fill("#ivFrom", "2026-01-01"); pg.dispatch_event("#ivFrom", "change"); pg.fill("#ivTo", "2026-01-31"); pg.dispatch_event("#ivTo", "change"); pg.wait_for_timeout(200)
    check("filter by date", rows() == ["Cedar Dental"])
    pg.click("#pg-invoices [data-clr]"); pg.wait_for_timeout(200)
    pg.click("#pg-invoices [data-iv]:has-text('Cedar Dental')"); pg.wait_for_selector(".iv-hero"); pg.click("[data-a=void]"); pg.wait_for_selector(".ov.on #ivVr")
    pg.fill("#ivVr", "Client cancelled"); pg.click(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(500)
    check("voiding uses its own dialog and keeps the invoice, marked void", pg.evaluate("()=>INV.cur.status") == "void" and "Client cancelled" in pg.inner_text(".iv-hero"))
    check("no page errors so far (admin)", not errs or print(errs))
    ctx.close()

    print("7. a teammate on a phone (Gio)")
    ctx, pg, errs2 = page(br, "gio", phone=True)
    open_invoices(pg)
    check("Gio doesn't see the admin's invoices", "No invoices yet" in pg.inner_text("#pg-invoices"))
    check("no Templates or Settings buttons for a teammate", not pg.query_selector("#pg-invoices [data-tpl]") and not pg.query_selector("#pg-invoices .pg-head [data-set]"))
    check("nothing sticks out sideways on a phone (list)", no_overflow(pg))
    pg.tap("#pg-invoices [data-new]"); pg.wait_for_selector("#ivCn")
    pg.fill("#ivCn", "Map"); pg.wait_for_timeout(900)
    sug = pg.evaluate("()=>[...document.querySelectorAll('#ivSug [data-k]')].map(b=>b.innerText)")
    check(f"client suggestions don't leak another person's invoices ({sug})", not any("Maple" in x for x in sug))
    pg.fill("#ivCn", "Willow Spa"); fill_item(pg, 0, "Website care plan", 3, 49.99)
    check("nothing sticks out sideways on a phone (editor)", no_overflow(pg))
    pg.tap("[data-save=sent]"); pg.wait_for_selector(".iv-hero", timeout=15000)
    cur = pg.evaluate("()=>INV.cur")
    check("Gio's invoice gets the next number for the team", cur["number"] == f"LF-{YEAR}-0004" and float(cur["total"]) == round(149.97 * 1.13, 2))
    check("Gio can't mark it paid or void it", not pg.query_selector("[data-a=pay]") and not pg.query_selector("[data-a=void]"))
    check("nothing sticks out sideways on a phone (invoice)", no_overflow(pg))
    r = pg.evaluate("async()=>api('sb_rpc','inv_pay',{p_id:INV.cur.id,p_amount:1,p_on:'2026-01-01',p_method:'Cash',p_ref:'',p_note:''})")
    check("and the database refuses it even if someone tries directly", r["ok"] is False and "administrator" in r["error"])

    print("8. team profile cards")
    pg.evaluate("async()=>{await go('account',true)}"); pg.wait_for_selector("#xCard"); pg.tap("#xCard"); pg.wait_for_selector(".ov.on #tcD")
    pg.fill("#tcD", "Sales"); pg.fill("#tcR", "Cold calls and follow-ups"); pg.fill("#tcS", "Cold calling, CRM, Web design"); pg.fill("#tcE", "gio@leaflineweb.com"); pg.fill("#tcP", "519-555-0199")
    pg.tap(".ov.on [data-ok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    pg.evaluate(f"()=>personModal(personFull('{ids['gio']}'))"); pg.wait_for_selector(".ov.on .pinfo .pchip")
    txt = pg.inner_text(".ov.on .pcard")
    check("Gio's card shows department, responsibilities, skills and contact", all(x in txt for x in ["Sales", "Cold calls and follow-ups", "CRM", "gio@leaflineweb.com", "519-555-0199", "Active account"]))
    check("Gio can edit his own card from it", pg.is_visible(".ov.on [data-edcard]"))
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    pg.evaluate(f"()=>personModal(personFull('{ids['tim']}'))"); pg.wait_for_selector(".ov.on .pcard")
    check("but not Tim's", not pg.query_selector(".ov.on [data-edcard]"))
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    r = pg.evaluate(f"async()=>api('sb_rpc','team_card_set',{{p_id:'{ids['tim']}',p_department:'X',p_responsibilities:'',p_skills:'',p_phone:'',p_email:''}})")
    check("and the database refuses it", r["ok"] is False)
    check("no page errors (phone)", not errs2 or print(errs2))
    ctx.close()

    print("9. the same profile everywhere, Kyle and Mubaraq (admin, PC size)")
    ctx, pg, errs3 = page(br, "james")
    pg.evaluate("async()=>{await go('admin',true)}"); pg.wait_for_selector(f"#pg-admin [data-au='{ids['kyle']}']", timeout=20000)
    check("Kyle and Mubaraq are on the Admin page as regular team members", all(pg.evaluate(f"()=>{{const r=document.querySelector(\"#pg-admin [data-au='{ids[n]}']\").closest('tr').innerText;return /Rep|employee|Employee/.test(r)&&!/\\bAdmin\\b/.test(r)}}") for n in ("kyle", "mubaraq")))
    pg.click(f"#pg-admin [data-au='{ids['gio']}']"); pg.wait_for_selector(".ov.on .pcard .pinfo .pchip", timeout=10000)
    check("clicking a name on the Admin page opens the same profile card, with the team card", "Cold calls and follow-ups" in pg.inner_text(".ov.on .pcard"))
    check("an admin can edit anyone's card", pg.is_visible(".ov.on [data-edcard]"))
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    names = pg.evaluate("()=>teamList().map(x=>x[1])")
    check(f"Kyle and Mubaraq are in the team pickers ({names})", "Kyle" in names and "Mubaraq" in names)
    cards = pg.evaluate("async()=>{await loadTeamCards(true);return Object.values(TEAMC.by).map(c=>[c.name,c.role,c.active])}")
    check("their team cards say regular, active accounts", ["Kyle", "employee", True] in cards and ["Mubaraq", "employee", True] in cards)
    pg.evaluate("async()=>{await go('team',true)}"); pg.wait_for_selector(f"#pg-team [data-pid='{ids['kyle']}']", timeout=20000)
    check("they're on the Team page", pg.is_visible(f"#pg-team [data-pid='{ids['mubaraq']}']"))
    t0 = time.time(); pg.click(f"#pg-team [data-pid='{ids['gio']}']"); pg.wait_for_selector(".ov.on .pinfo .pchip"); dt = time.time() - t0
    check(f"the card opens instantly, already loaded ({dt:.2f}s)", dt < 1.5)
    check("the Team page shows the department", "Sales" in pg.inner_text(f"#pg-team [data-pid='{ids['gio']}']"))
    check("no page errors (admin)", not errs3 or print(errs3))
    ctx.close()

    print("10. Kyle signs in: a regular account")
    ctx, pg, errs4 = page(br, "kyle")
    check("no Admin page for Kyle", not pg.is_visible("#nav [data-go=admin]"))
    open_invoices(pg)
    check("Kyle starts with no invoices and no admin buttons", "No invoices yet" in pg.inner_text("#pg-invoices") and not pg.query_selector("#pg-invoices [data-tpl]"))
    r = pg.evaluate("async()=>api('sb_rpc','inv_settings_set',{p:{footer:'x'}})")
    check("the database refuses admin settings for Kyle", r["ok"] is False and "administrator" in r["error"])
    check("no page errors (Kyle)", not errs4 or print(errs4))
    ctx.close()

    print("11. before the 14th database update")
    url, F.msg_url = F.msg_url, None
    ctx, pg, errs5 = page(br, "tim")
    open_invoices(pg)
    check("Invoices explains the update is needed instead of breaking", "14th database update" in pg.inner_text("#pg-invoices"))
    pg.evaluate(f"()=>personModal(personFull('{ids['gio']}'))"); pg.wait_for_selector(".ov.on .pcard")
    check("profiles still open (without the extra details)", pg.is_visible(".ov.on .pcard h2"))
    check("no page errors (old database)", not errs5 or print(errs5))
    ctx.close(); F.msg_url = url

    print("12. the PC app (desktop engine)")
    os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
    import leafline_backend as B
    api = B.Api(db=B.open_db(os.path.join(os.environ["HOME"], "t.db")), profile_path=os.path.join(os.environ["HOME"], "p.json")); api._ready.set()
    assert api.sign_in("tim", "Tim123")["ok"]
    t0 = time.time()
    while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.3)
    dsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler); dport = dsrv.server_address[1]
    dsrv.RequestHandlerClass = B.make_handler(api, dport, "tok"); dsrv.daemon_threads = True; threading.Thread(target=dsrv.serve_forever, daemon=True).start()
    pg = br.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True); errs6 = []; pg.on("pageerror", lambda e: errs6.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto(f"http://127.0.0.1:{dport}/?t=tok&nointro"); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    open_invoices(pg)
    pg.click("#pg-invoices [data-new]"); pg.wait_for_selector("#ivCn"); pg.fill("#ivCn", "Pine Auto"); fill_item(pg, 0, "Car wrap", 1, 2500)
    pg.click("[data-save=sent]"); pg.wait_for_selector(".iv-hero", timeout=15000)
    check("the PC app makes invoices through the same database", pg.evaluate("()=>INV.cur.number") == f"LF-{YEAR}-0005")
    pdf, _ = pdf_of(pg)
    check("and the PDF downloads there too", pdf[:5] == b"%PDF-")
    api._sync.stop.set()
    check("no page errors (PC app)", not errs6 or print(errs6))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
