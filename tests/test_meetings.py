"""11.13: confirming meetings happened, and the pop-up on app open for meetings and payments that passed without being
confirmed. Runs the real WEBSITE build (phone and PC sizes) against the fake shared database."""
import os, sys, tempfile, threading, http.server, functools
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
TZ = ZoneInfo("America/Toronto"); NOW = datetime.now(TZ).replace(second=0, microsecond=0)
at = lambda days, h=10: (NOW - timedelta(days=days)).replace(hour=h, minute=0)
key = lambda d: d.strftime("%Y-%m-%d %H:%M")
M = {"g1": at(3), "g2": at(2, 14), "g3": NOW + timedelta(days=4), "g4": at(3, 11), "g5": at(60)}
WHO = {"g1": "gio", "g2": "gio", "g3": "gio", "g4": "tim", "g5": "gio"}
for i, (lid, when) in enumerate(M.items()):
    F.t["leads"].append(dict(id=lid, name=f"Meeting Co {lid}", phone=f"(519) 555-03{i:02d}", owner_name="N/A", email="N/A", rating="4.5", reviews="10", website="N/A",
                             address="N/A", search="Roofing | Kitchener", btype="Roofing", hours="", status="green", notes="", enriched=False,
                             added_at="2026-10-01T14:00:00+00:00", called_at=at(10).isoformat(), meeting_at=when.isoformat(), called_by=ids[WHO[lid]],
                             version=1, updated_at=F.now(), created_at=F.now(), phone_key=f"51955503{i:02d}"))
PAYDAY = (NOW - timedelta(days=5)).date().isoformat()
F.t["deals"].append(dict(id="d0000000-0000-4000-8000-0000000000b1", client="Birch Dental", upfront=750, monthly=0, months=0, closed_at=PAYDAY, first_bill=PAYDAY,
                         notes="", owner_id=ids["james"], confirmed="", version=1, updated_at=F.now(), created_at=F.now()))
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
def page(br, who, phone=False, due=True):
    o = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=UA) if phone else dict(viewport={"width": 1440, "height": 900})
    ctx = br.new_context(**o); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?nointro" + ("&due" if due else "")); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    return ctx, pg, errs
def wait_due(pg, t=20000):
    pg.wait_for_selector(".ov.on .due", timeout=t); pg.wait_for_timeout(400)
ROWS = "()=>[...document.querySelectorAll('.ov.on .drow')].map(r=>r.dataset.m||r.dataset.p)"
def checked(lid): return any(m["lead_id"] == lid and m["meeting_key"] == key(M[lid]) for m in F.t["meeting_checks"])

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    print("1. the pop-up on a phone (Gio)")
    ctx, pg, errs = page(br, "gio", phone=True)
    wait_due(pg)
    rows = pg.evaluate(ROWS)
    check(f"opening the app asks about Gio's own meetings that passed in the last 30 days ({rows})", rows == ["g1", "g2"])
    check("no payments for someone who isn't an admin", "Payments" not in pg.inner_text(".ov.on"))
    check("big buttons on a phone, nothing off-screen", pg.evaluate("()=>[...document.querySelectorAll('.ov.on .drow .dbtn .btn')].every(b=>b.getBoundingClientRect().height>=44&&b.getBoundingClientRect().right<=innerWidth)"))
    pg.tap(".ov.on [data-m='g1'] [data-mok]"); pg.wait_for_timeout(900)
    check("'It happened' confirms the meeting for that exact time", checked("g1") and pg.evaluate(ROWS) == ["g2"])
    pg.tap(".ov.on [data-m='g2'] [data-mnew]"); pg.wait_for_timeout(200)
    new = (NOW + timedelta(days=2)).replace(hour=15, minute=30)
    pg.fill(".ov.on [data-m='g2'] .dnew input", new.strftime("%Y-%m-%dT%H:%M")); pg.tap(".ov.on [data-m='g2'] [data-msave]")
    pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(2500)
    g2 = next(l for l in F.t["leads"] if l["id"] == "g2")
    check("'New time' moves the meeting, and the pop-up closes when everything is handled", datetime.fromisoformat(g2["meeting_at"]).astimezone(TZ).strftime("%Y-%m-%d %H:%M") == key(new))
    pg.reload(); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000); pg.wait_for_timeout(5000)
    check("next time the app opens there's nothing to ask", not pg.query_selector(".ov.on .due"))
    print("2. the Confirm meeting button on Called Leads")
    pg.evaluate("async()=>{document.querySelectorAll('.ov').forEach(x=>x.remove());await go('called');await new Promise(r=>setTimeout(r,1200))}")
    pg.evaluate("()=>{const b=document.querySelector('#pg-called [data-show]');}")
    card = lambda lid: pg.evaluate("(id)=>{const c=document.querySelector(`#pg-called .kc[data-id='${id}']`);return c?c.innerText:''}", lid)
    check("a past meeting nobody confirmed shows 'Confirm meeting' (Tim's, any teammate can confirm)", "Confirm meeting" in card("g4"))
    check("a confirmed one shows 'Met'", "Met" in card("g1") and "Confirm meeting" not in card("g1"))
    check("an upcoming meeting has no button yet", "Confirm meeting" not in card("g3") and "Met" not in card("g3"))
    pg.evaluate("()=>document.querySelector(\"#pg-called .kc[data-id='g4'] [data-mcf]\").click()"); pg.wait_for_timeout(1200)
    check("pressing it confirms the meeting and the card shows 'Met'", checked("g4") and "Met" in card("g4"))
    print("3. in the business pop-up")
    pg.evaluate("()=>leadModal(S.called.find(l=>l.id==='g5'))"); pg.wait_for_selector(".ov.on [data-mconf]")
    check("an old unconfirmed meeting asks 'Did this meeting happen?'", "Did this meeting happen?" in pg.inner_text(".ov.on"))
    pg.tap(".ov.on [data-mconf]"); pg.wait_for_selector(".ov.on .mline.ok", timeout=10000)
    check("Confirm meeting there works too", checked("g5"))
    pg.tap(".ov.on [data-mundo]"); pg.wait_for_selector(".ov.on [data-mconf]", timeout=10000)
    check("...and Undo takes it back", not checked("g5"))
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    pg.evaluate("()=>leadModal(S.called.find(l=>l.id==='g3'))"); pg.wait_for_selector(".ov.on .mline")
    check("an upcoming meeting says it can be confirmed after its time", "Upcoming" in pg.inner_text(".ov.on .mline") and not pg.query_selector(".ov.on [data-mconf]"))
    ctx.close()

    print("4. an admin also sees payments (PC size)")
    ctx, pg, errs2 = page(br, "james")
    wait_due(pg)
    rows = pg.evaluate(ROWS)
    check(f"James (admin, no meetings of his own) is asked about the unconfirmed payment ({rows})", rows == [f"d0000000-0000-4000-8000-0000000000b1|{PAYDAY}|upfront"] or (len(rows) == 1 and rows[0].endswith(f"|{PAYDAY}|upfront")))
    check("it shows the client and amount", "Birch Dental" in pg.inner_text(".ov.on") and "$750" in pg.inner_text(".ov.on"))
    pg.click(".ov.on [data-pedit]"); pg.wait_for_timeout(900)
    check("'Change dates' opens that deal to change its dates", pg.is_visible(".ov.on") and "Birch Dental" in pg.evaluate("()=>[...document.querySelectorAll('.ov.on input')].map(i=>i.value).join(' ')"))
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    pg.evaluate("()=>{S.dueShown=false;maybeDuePopup()}"); wait_due(pg)
    pg.click(".ov.on [data-pok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000); pg.wait_for_timeout(3000)
    d = F.t["deals"][0]
    check("'Received' confirms the payment (it now counts as made)", f"{PAYDAY}:upfront" in (d.get("confirmed") or ""))
    print("5. before the 13th database update")
    F.mtg_cap = False
    pg.evaluate("async()=>{MTG.at=0;await loadMtg(true);await go('called')}"); pg.wait_for_timeout(800)
    r = pg.evaluate("async()=>{const l=S.called.find(x=>x.id==='g1');const msgs=[];const t=window.toast;window.toast=m=>msgs.push(m);const ok=await confirmMeeting(l,false);window.toast=t;return [ok,msgs]}")
    check("confirming says the 13th update is needed, nothing breaks", r[0] is False and any("13th database update" in m for m in r[1]))
    check("no meeting questions pop up while it can't be saved", pg.evaluate("()=>dueMeetings().length") == 0)
    F.mtg_cap = True
    ctx.close()

    print("6. the PC app (desktop engine)")
    os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
    import time
    import leafline_backend as B
    F.t["meeting_checks"][:] = [m for m in F.t["meeting_checks"] if m["lead_id"] != "g4"]
    F.t["deals"][0]["confirmed"] = ""
    api = B.Api(db=B.open_db(os.path.join(os.environ["HOME"], "t.db")), profile_path=os.path.join(os.environ["HOME"], "p.json")); api._ready.set()
    assert api.sign_in("tim", "Tim123")["ok"]
    t0 = time.time()
    while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.3)
    dsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler); dport = dsrv.server_address[1]
    dsrv.RequestHandlerClass = B.make_handler(api, dport, "tok"); dsrv.daemon_threads = True; threading.Thread(target=dsrv.serve_forever, daemon=True).start()
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs3 = []; pg.on("pageerror", lambda e: errs3.append(str(e)))
    pg.goto(f"http://127.0.0.1:{dport}/?t=tok&nointro&due"); wait_due(pg)
    check(f"on the PC, Tim is asked about his own meeting ({pg.evaluate(ROWS)})", pg.evaluate(ROWS) == ["g4"])
    pg.click(".ov.on [data-m='g4'] [data-mok]"); pg.wait_for_function("!document.querySelector('.ov.on')", timeout=15000)
    check("...and confirming it on the PC saves it for everyone", checked("g4"))
    api._sync.stop.set()
    check("no page errors", not (errs + errs2 + errs3) or print(errs + errs2 + errs3))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
