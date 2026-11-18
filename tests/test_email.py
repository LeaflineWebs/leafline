"""11.20 email writer: Find Leads (Email button), Called Leads (Write email), the after-call card, the plain-template
fallback and the PC app's engine. Runs the real WEBSITE build (PC and phone sizes) against the fake shared database, whose
stand-in for the email-draft Edge Function echoes what it was sent. The function's real request handling is tested in
tests/fn/test_email_draft.mjs and the 18th update's database rules in tests/pg/test_email_sql.mjs."""
import os, sys, tempfile, threading, http.server, functools, time, json, requests
from datetime import datetime, timedelta, timezone
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
NOW = datetime.now(timezone.utc); iso = lambda d: d.isoformat()
def lead(i, name, phone, status="none", web="N/A", owner="N/A", notes="", by=None, ago=None, meeting=None, email="N/A"):
    F.t["leads"].append(dict(id=i, name=name, phone=phone, owner_name=owner, email=email, rating="4.8", reviews="3", website=web, address="1 King St, London ON",
        search="Roofers | London", btype="Roofer", hours="", status=status, notes=notes, enriched=False, added_at=iso(NOW - timedelta(days=30)),
        called_at=iso(NOW - timedelta(days=ago)) if ago is not None else None, meeting_at=meeting, called_by=by and ids[by], version=1, updated_at=F.now(), created_at=F.now(),
        phone_key="".join(c for c in phone if c.isdigit())[-10:]))
lead("L1", "Maple Roofing", "(519) 555-0101", owner="Sam Lee")
lead("L2", "Oak Roofing", "519-555-0102", web="https://oak.ca")
lead("L3", "Cedar Roofing", "519-555-0103")
lead("L4", "Elm Roofing", "519-555-0104")
lead("L5", "Fir Roofing", "519-555-0105")
lead("L7", "Spruce Roofing", "519-555-0107")
lead("L6", "Birch Roofing", "519-555-0106", web="https://birchroofing.ca", email="hello@birchroofing.ca")
lead("P1", "Pine Roofing", "519-555-0201", "yellow", owner="Ana Ruiz", notes="Wants a quote by Friday", by="gio", ago=1)
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
SHOTS = os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp()
def page(br, who, phone=False):
    o = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True) if phone else dict(viewport={"width": 1440, "height": 900})
    ctx = br.new_context(**o); pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300])); pg.on("dialog", lambda d: d.accept())
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())"); pg.wait_for_timeout(300)
    pg.evaluate("()=>{window.__mail=[];window.invMailto=u=>window.__mail.push(u);window.__open=[];window.open=(u)=>{window.__open.push(u);return null}}")
    return ctx, pg
def find_all(pg):
    pg.evaluate("async()=>{await go('find',true);$('#scope').value='all';$('#scope').dispatchEvent(new Event('change'))}"); pg.wait_for_timeout(1200)
def pick(pg, lid):
    pg.evaluate(f"()=>{{S.active='{lid}';lastDetail=null;renderFind()}}"); pg.wait_for_timeout(250)
last = lambda: F.email_reqs[-1]["body"] if F.email_reqs else {}

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    ctx, pg = page(br, "gio")

    print("1. Find Leads: Email button")
    find_all(pg); pick(pg, "L1")
    check("the business details have an Email button", pg.is_visible("#detail #dMail"))
    pg.fill("#dNotes", "Roof photos on Facebook only"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.wait_for_timeout(350)
    check("the pop-up is for that business, with a prompt box, quick picks and tones", "Email Maple Roofing" in pg.inner_text(".ov.on h2")
          and len(pg.query_selector_all(".ov.on [data-pick]")) == 6 and len(pg.query_selector_all(".ov.on [data-tone]")) == 3)
    check("nothing is written until you ask, but the send buttons are ready to press, with a tip", pg.evaluate("()=>$('#emOut').hidden&&!$('#emSend').disabled&&!$('#emGmail').disabled&&!$('#emCopy').disabled&&!!$('#emHint')"))
    check("the prompt box has focus, ready to type", pg.evaluate("()=>document.activeElement&&document.activeElement.id==='emAsk'"))
    pg.click(".ov.on [data-pick='1']")
    check("a quick pick fills the prompt", "free mock-up" in pg.input_value("#emAsk"))
    pg.fill("#emAsk", "Offer a free homepage mock-up and ask for 15 minutes Thursday"); pg.click(".ov.on [data-tone='professional']")
    pg.click("#emGo"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    b = last()
    check("the email writer gets the business, the call notes you just typed, the prompt and the tone", b.get("lead", {}).get("name") == "Maple Roofing" and b["lead"]["owner"] == "Sam Lee"
          and b["lead"]["notes"] == "Roof photos on Facebook only" and b["lead"]["website"] == "N/A" and b["prompt"].startswith("Offer a free homepage") and b["tone"] == "professional" and b["kind"] == "", b)
    check("...and who is sending it", b.get("sender", {}).get("name") == "Gio" and b["sender"]["company"] == "Leafline Web Services", b.get("sender"))
    check("...with Gio's own sign-in (the fake checks the token)", F.email_reqs[-1]["uid"] == ids["gio"])
    body = pg.input_value("#emBody")
    check("a full email comes back: subject, greeting by first name, and the signature added under it", pg.input_value("#emSub") == "A new website for Maple Roofing"
          and body.startswith("Hi Sam,") and body.rstrip().endswith("Best,\nGio\nLeafline Web Services"), body)
    check("the count for today is shown, and the AI result is flagged to be read over", "1 of 150 emails today" in pg.inner_text("#emMsg") and "Read it over" in pg.inner_text("#emMsg"))
    check("Open in Gmail is the main button, and the tip is gone once there's an email", pg.evaluate("()=>$('#emGmail').classList.contains('pri')&&!$('#emHint')"))
    pg.screenshot(path=os.path.join(SHOTS, "email_pc.png"))
    pg.click(".em-sig summary"); pg.fill("#emSig", "Gio Rossi\nSales, Leafline\n519-555-0000"); pg.dispatch_event("#emSig", "change"); pg.wait_for_timeout(200)
    body = pg.input_value("#emBody")
    check("editing the signature swaps it at the bottom of the email", body.endswith("Best,\nGio Rossi\nSales, Leafline\n519-555-0000") and body.count("Leafline Web Services") == 0, body)
    pg.fill("#emTo", "sam@mapleroofing.ca"); pg.click("#emSend"); pg.wait_for_timeout(200)
    m = pg.evaluate("()=>window.__mail[0]||''")
    check("Email app: to, subject and the whole email go to the email app", m.startswith("mailto:sam%40mapleroofing.ca?subject=A%20new%20website%20for%20Maple%20Roofing&body=Hi%20Sam%2C") and "Gio%20Rossi" in m, m[:200])
    pg.click("#emGmail"); pg.wait_for_timeout(100)
    gm = pg.evaluate("()=>window.__open[0]||''")
    check("Gmail opens a filled-in new email", gm.startswith("https://mail.google.com/mail/?view=cm&fs=1&to=sam%40mapleroofing.ca&su=A%20new%20website") and "body=Hi%20Sam" in gm, gm[:200])
    pg.click("#emGo"); pg.wait_for_function("()=>$('#emMsg').innerText.includes('2 of 150')", timeout=20000)
    check("Write again makes a new one", len(F.email_reqs) == 2)
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    prefs = pg.evaluate("()=>[getP('emailTone'),getP('emailSig')]")
    check("the tone and the signature are remembered", prefs == ["professional", "Gio Rossi\nSales, Leafline\n519-555-0000"], prefs)
    pick(pg, "L2"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg")
    check("...next time: Professional is already picked", pg.evaluate("()=>$('.ov.on [data-tone=\"professional\"]').classList.contains('on')"))
    pg.press("#emAsk", "Control+Enter"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    body = pg.input_value("#emBody")
    check("Ctrl+Enter writes it; no owner name = 'Hi <business> team,'; the saved signature is used", body.startswith("Hi Oak Roofing team,") and body.endswith("Gio Rossi\nSales, Leafline\n519-555-0000"), body)
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)

    n0 = len(F.email_reqs)
    pick(pg, "L4"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.fill("#emAsk", "Offer a free audit")
    pg.evaluate("()=>{window.__open=[]}"); pg.click("#emGmail"); pg.wait_for_function("()=>window.__open.some(u=>u.startsWith('https://mail.google.com'))", timeout=20000)
    op = pg.evaluate("()=>window.__open")
    check("one click: 'Open in Gmail' with no email yet writes it, then opens it in Gmail", len(F.email_reqs) == n0 + 1 and last()["prompt"] == "Offer a free audit"
          and "su=A%20new%20website%20for%20Elm%20Roofing" in op[-1] and "AI%20email%20about%3A%20Offer%20a%20free%20audit" in op[-1], op)
    check("...and shows what it sent, so you can see it", pg.input_value("#emSub") == "A new website for Elm Roofing")
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    pick(pg, "L5"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.evaluate("()=>{window.__mail=[]}"); pg.click("#emSend")
    pg.wait_for_function("()=>window.__mail.length", timeout=20000)
    check("'Email app' with no email yet also writes it first, then opens it", pg.evaluate("()=>window.__mail[0]").startswith("mailto:?subject=A%20new%20website%20for%20Fir%20Roofing"))
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    F.t["email_drafts"].extend(dict(id=2000 + i, user_id=ids["gio"], lead_id="y", created_at=F.now()) for i in range(150))
    pick(pg, "L2"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.evaluate("()=>{window.__open=[]}"); pg.click("#emGmail"); pg.wait_for_timeout(1500)
    check("if it can't write one (daily limit), nothing is opened and the reason is shown", not any(u.startswith("https://mail.google") for u in pg.evaluate("()=>window.__open")) and "150 emails" in pg.inner_text("#emMsg"))
    F.t["email_drafts"][:] = [r for r in F.t["email_drafts"] if r["lead_id"] != "y"]
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)

    print("2. Right after a call")
    pick(pg, "L3"); pg.fill("#dNotes", "Owner is Dave, call after 3"); pg.evaluate("async()=>{await markLeads('yellow')}")
    pg.wait_for_selector(".ov.on", timeout=5000); pg.wait_for_timeout(1200)
    check("Interested opens the reminder pop-up first; the email offer waits behind it", not pg.query_selector("#emNudge.on"))
    pg.keyboard.press("Escape"); pg.wait_for_selector("#emNudge.on", timeout=5000)
    check("marking Interested offers to write the email", "Email Cedar Roofing?" in pg.inner_text("#emNudge"))
    pg.screenshot(path=os.path.join(SHOTS, "email_nudge.png"))
    n0 = len(F.email_reqs); pg.click("#emNudge [data-emgo]"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    b = last()
    check("one tap writes it straight away, from the call result and the notes", len(F.email_reqs) == n0 + 1 and b["kind"] == "interested" and b["lead"]["notes"] == "Owner is Dave, call after 3"
          and "recap what we talked about" in b["prompt"], b)
    check("the pop-up says what happened on the call", "Interested" in pg.inner_text(".ov.on .em-sub"))
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    check("the card is gone after using it", not pg.is_visible("#emNudge.on"))
    pick(pg, "L4"); pg.evaluate("async()=>{await markLeads('red')}"); pg.wait_for_timeout(700)
    check("Not interested: no email offered", not pg.query_selector("#emNudge.on"))
    pick(pg, "L5"); pg.evaluate("async()=>{await markLeads('orange')}"); pg.wait_for_selector("#emNudge.on", timeout=5000)
    check("No answer offers it too", "Email Fir Roofing?" in pg.inner_text("#emNudge"))
    pg.click("#emNudge [data-emx]"); pg.wait_for_timeout(500)
    check("...and × dismisses it without writing anything", not pg.query_selector("#emNudge.on") and not pg.query_selector(".ov.on .em-dlg"))

    print("3. Called Leads")
    pg.evaluate("async()=>{await go('called',true)}"); pg.wait_for_timeout(1200)
    pg.evaluate("()=>leadModal(S.called.find(x=>x.id==='P1'))"); pg.wait_for_selector(".ov.on [data-mail]")
    pg.click(".ov.on [data-mail]"); pg.wait_for_selector(".ov.on .em-dlg", timeout=5000)
    check("Write email in the Called Leads pop-up starts from the result (Interested), ready to edit", "Email Pine Roofing" in pg.inner_text(".ov.on h2")
          and "recap what we talked about" in pg.input_value("#emAsk") and pg.evaluate("()=>$('#emOut').hidden"))
    pg.click("#emGo"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    check("...with the notes saved on that business", last()["lead"]["notes"] == "Wants a quote by Friday" and pg.input_value("#emBody").startswith("Hi Ana,"), last())
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    pg.evaluate("()=>logCallModal(S.called.find(x=>x.id==='P1'))"); pg.wait_for_selector(".ov.on #lcOut")
    pg.click(".ov.on [data-o='voicemail']"); pg.fill("#lcNotes", "left vm at 2pm"); pg.click(".ov.on [data-save]")
    pg.wait_for_selector("#emNudge.on", timeout=8000)
    pg.click("#emNudge [data-emgo]"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    check("logging a call (Voicemail) offers it too, with the call's notes", last()["kind"] == "voicemail" and last()["lead"]["notes"] == "left vm at 2pm", last())
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)

    print("4. When the AI isn't available")
    F.email_fn = "none"; find_all(pg); pick(pg, "L1"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.click("#emGo")
    pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    body = pg.input_value("#emBody")
    check("not set up yet: a proper plain template is filled in (first name, about them, a next step, signature)", body.startswith("Hi Sam,") and "Maple Roofing doesn't have a website yet" in body
          and "10-minute call" in body and body.endswith("519-555-0000") and pg.input_value("#emSub") == "A website for Maple Roofing", body)
    check("...and it says so, and how to set it up", "isn't set up yet" in pg.inner_text("#emMsg") and "SETUP_SUPABASE.md" in pg.inner_text("#emMsg"))
    F.email_fn = "nokey"; pg.click("#emGo"); pg.wait_for_timeout(1200)
    check("no AI key in Supabase: same clear message", "isn't set up yet" in pg.inner_text("#emMsg"))
    F.email_fn = "ok"; F.email_cap = False; pg.click("#emGo"); pg.wait_for_timeout(1200)
    check("18th update not run: says that, template still filled in", "18th database update" in pg.inner_text("#emMsg") and pg.input_value("#emBody").startswith("Hi Sam,"))
    F.email_cap = True; F.email_fn = "busy"; pg.click("#emGo"); pg.wait_for_timeout(1200)
    check("AI busy: says so, template filled in", "busy" in pg.inner_text("#emMsg"))
    F.email_fn = "ok"
    F.t["email_drafts"].extend(dict(id=1000 + i, user_id=ids["gio"], lead_id="x", created_at=F.now()) for i in range(150))
    pg.fill("#emSub", "kept"); pg.click("#emGo"); pg.wait_for_timeout(1200)
    check("over the daily limit: the reason is shown and what you had isn't replaced", "150 emails in the last 24 hours" in pg.inner_text("#emMsg") and pg.input_value("#emSub") == "kept")
    F.t["email_drafts"][:] = [r for r in F.t["email_drafts"] if r["lead_id"] != "x"]
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    ctx.close()

    print("5. Phone size")
    ctx, pg = page(br, "tim", phone=True)
    find_all(pg); pick(pg, "L1"); pg.evaluate("()=>openDetailSheet()"); pg.wait_for_timeout(400)
    check("the Email button is in the business pop-up on a phone", pg.is_visible("#detail #dMail"))
    pg.click("#detail #dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.fill("#emAsk", "Short intro"); pg.click("#emGo")
    pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    pg.screenshot(path=os.path.join(SHOTS, "email_phone.png"))
    check("it fits the phone (no sideways scrolling)", pg.evaluate("()=>document.documentElement.scrollWidth<=innerWidth&&$('.ov.on .dlg').scrollWidth<=$('.ov.on .dlg').clientWidth+1"))
    check("Tim's signature is his own", pg.input_value("#emBody").endswith("Tim\nLeafline Web Services"), pg.input_value("#emBody")[-60:])
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    pg.evaluate("()=>emailNudge(S.find.find(x=>x.id==='L2'),'no_answer')"); pg.wait_for_selector("#emNudge.on")
    box = pg.evaluate("()=>{const r=$('#emNudge').getBoundingClientRect(),t=$('.btmbar')||$('.tabbar')||$('nav.bb');return {l:r.left,r:r.right,b:r.bottom,w:innerWidth,h:innerHeight}}")
    check(f"the after-call card sits inside the screen, above the bottom bar ({box})", box["l"] >= 0 and box["r"] <= box["w"] and box["b"] < box["h"] - 100)
    ctx.close()

    print("7. Emails found on business websites")
    ctx, pg = page(br, "gio"); find_all(pg); pick(pg, "L6")
    check("Find Leads shows the email found on the business's website", pg.input_value("#detail #dEmail") == "hello@birchroofing.ca")
    pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg"); pg.click("#emGo"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    check("...and the email pop-up's To box is already filled in with it", pg.input_value("#emTo") == "hello@birchroofing.ca")
    pg.evaluate("()=>{window.__open=[]}"); pg.click("#emGmail"); pg.wait_for_timeout(300)
    check("...so Open in Gmail has the address too", "to=hello%40birchroofing.ca" in (pg.evaluate("()=>window.__open[0]||''")))
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    lr = lambda i: next(l for l in F.t["leads"] if l["id"] == i)
    pick(pg, "L2"); pg.fill("#dEmail", "not an email"); pg.evaluate("async()=>{await saveDetail(false)}"); pg.wait_for_timeout(1500)
    check("typing something that isn't an email is refused with a message, nothing saved", "doesn't look right" in pg.inner_text("#toast") and lr("L2")["email"] == "N/A")
    pg.fill("#dEmail", "owner@oakroofing.ca"); pg.evaluate("async()=>{await saveDetail(false)}")
    t0 = time.time()
    while lr("L2")["email"] != "owner@oakroofing.ca" and time.time() - t0 < 20: time.sleep(.3)
    check("typing an email in Find Leads saves it to the shared database", lr("L2")["email"] == "owner@oakroofing.ca", lr("L2")["email"])
    pick(pg, "L7"); pg.click("#dMail"); pg.wait_for_selector(".ov.on .em-dlg")
    check("no email known: the To box starts empty", pg.input_value("#emTo") == "")
    pg.click("#emGo"); pg.wait_for_function("()=>!$('#emOut').hidden&&$('#emBody').value", timeout=20000)
    pg.fill("#emTo", "info@spruceroofing.ca"); pg.evaluate("()=>{window.__mail=[]}"); pg.click("#emSend")
    t0 = time.time()
    while lr("L7")["email"] != "info@spruceroofing.ca" and time.time() - t0 < 20: time.sleep(.3)
    check("an address typed in the To box is saved on the business for next time", lr("L7")["email"] == "info@spruceroofing.ca", lr("L7")["email"])
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    pg.evaluate("async()=>{await go('called',true)}"); pg.wait_for_timeout(1000)
    pg.evaluate("()=>leadModal(S.called.find(x=>x.id==='P1'))"); pg.wait_for_selector(".ov.on #mEmail")
    pg.fill("#mEmail", "ana@pineroofing.ca"); pg.click(".ov.on [data-save]")
    t0 = time.time()
    while lr("P1")["email"] != "ana@pineroofing.ca" and time.time() - t0 < 20: time.sleep(.3)
    check("Called Leads has an Email box too, and it saves", lr("P1")["email"] == "ana@pineroofing.ca", lr("P1")["email"])
    ctx.close()
    ctx, pg = page(br, "tim", phone=True); find_all(pg); pick(pg, "L6"); pg.evaluate("()=>openDetailSheet()"); pg.wait_for_timeout(400)
    ph = pg.evaluate("()=>({v:($('#detail #dEmail')||{}).value,w:document.documentElement.scrollWidth,iw:innerWidth,act:S.active})")
    check("on a phone the Email box is there and fits", ph["v"] == "hello@birchroofing.ca" and ph["w"] <= ph["iw"], ph)
    ctx.close()

    print("6. The PC app (desktop engine)")
    os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
    import leafline_backend as B
    check("the PC app's page has the email writer", "function emailModal(" in B.UI_HTML and 'id="dMail"' in B.UI_HTML and "data-mail" in B.UI_HTML)
    api = B.Api(db=B.open_db(os.path.join(os.environ["HOME"], "t.db")), profile_path=os.path.join(os.environ["HOME"], "p.json")); api._ready.set()
    assert api.sign_in("gio", "Gio123")["ok"]
    s = api.sb_session()
    check("the PC app hands the page its own sign-in (and only the public key)", s.get("ok") and s["url"] == F.url and s["token"] and "secret" not in json.dumps(s), {k: s.get(k) for k in ("ok", "url")})
    r = requests.post(s["url"] + "/functions/v1/email-draft", json={"lead": {"id": "L1", "name": "Maple Roofing", "owner": "Sam Lee"}, "prompt": "hi"},
                      headers={"Authorization": "Bearer " + s["token"], "apikey": s["key"] or ""}, timeout=10).json()
    check("...which the email writer accepts", r.get("ok") and r["body"].startswith("Hi Sam,"), r)
    # finding emails on a business's website (the PC app checks each website after a search)
    hidden = "5a" + bytes(c ^ 0x5a for c in b"service@elmauto.ca").hex()
    class Site(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def do_GET(s):
            pages = {"/": '<html><body><h1>Elm Auto</h1><img src="logo@2x.png"><a href="/contact-us">Contact</a><script>var e="dev@example.com"</script></body></html>',
                     "/contact-us": '<p>Owner: Dave Smith</p><a href="/cdn-cgi/l/email-protection" data-cfemail="' + hidden + '">[email protected]</a> noreply@elmauto.ca'}
            b = pages.get(s.path, "").encode(); s.send_response(200 if b else 404); s.send_header("Content-Type", "text/html"); s.end_headers(); s.wfile.write(b)
    ws = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site); threading.Thread(target=ws.serve_forever, daemon=True).start()
    got = B.enrich(f"http://127.0.0.1:{ws.server_address[1]}/")
    check(f"a business website's contact page gives up its email, even when Cloudflare hides it ({got})", got[3] == "service@elmauto.ca")
    cases = {('<a href="mailto:Info@MapleRoofing.ca?subject=Hi">x</a> sam@gmail.com', "https://www.mapleroofing.ca"): "info@mapleroofing.ca",
             ("Email: owner [at] pinespa [dot] com", "pinespa.com"): "owner@pinespa.com",
             ("logo@2x.png a1b2c3d4e5f6a7b8c9d0@sentry.wixpress.com you@example.com noreply@x.ca", "x.ca"): "N/A",
             ("call us, no email here", "x.ca"): "N/A"}
    bad = {k[0][:30]: (B.find_email(*k), v) for k, v in cases.items() if B.find_email(*k) != v}
    check("it prefers the business's own address and skips images, placeholders, no-reply and tracking addresses", not bad, bad)
    import leafline_sync as LS
    m, _ = LS.merge3({"notes": "a"}, {"notes": "b", "email": "N/A"}, {"notes": "a", "email": "found@biz.ca"}, True)
    check("sync: an email found on another computer is never wiped by a computer that doesn't know it yet", m == {"notes": "b", "email": "found@biz.ca"}, m)
    check("typing a bad email in the PC app is refused", api.save_email("L1", "nope").get("ok") is False and api.save_lead("L1", "Sam Lee", "", "bad@").get("ok") is False)
    t0 = time.time()
    while not any(l["id"] == "L1" for l in api.get_find("all")) and time.time() - t0 < 30: time.sleep(.3)
    r = api.save_email("L1", "sam@mapleroofing.ca"); api._sync.kick()
    t0 = time.time()
    while next(l for l in F.t["leads"] if l["id"] == "L1")["email"] != "sam@mapleroofing.ca" and time.time() - t0 < 30: time.sleep(.3)
    check("the PC app saves an email and it reaches the shared database", r.get("ok") and next(l for l in F.t["leads"] if l["id"] == "L1")["email"] == "sam@mapleroofing.ca")
    l2 = next(l for l in F.t["leads"] if l["id"] == "L2"); l2.update(email="hi@oak.ca", version=l2.get("version", 1) + 1, updated_at=F.now()); api._sync.kick()
    t0 = time.time()
    while next((l.get("email") for l in api.get_find("all") if l["id"] == "L2"), None) != "hi@oak.ca" and time.time() - t0 < 40: time.sleep(.5); api._sync.kick()
    check("an email found elsewhere shows up in the PC app", next((l.get("email") for l in api.get_find("all") if l["id"] == "L2"), None) == "hi@oak.ca")
    api._sync.stop.set()
    check("no page errors", not errs, errs[:3])
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
