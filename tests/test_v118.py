"""11.8: account details follow you between devices, leaderboard positions, centred theme buttons, no clipped Team
cards, roomy call notes, chat box focus, profile picture cropping, light/dark note pages, the new dashboard banner,
and lighter pictures / cached chats."""
import os, sys, tempfile, threading, io
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "james", "tim", "omar")}
for p in F.t["profiles"]: p["must_change_password"] = False
from datetime import datetime, timedelta, timezone
for i, st in enumerate(("yellow", "orange", "green", "yellow", "none", "none")):
    when = (datetime.now(timezone.utc) - timedelta(days=i)).isoformat()
    F.t["leads"].append(dict(id=f"lead{i}", name=f"Roofing Pro {i}", phone=f"(416) 555-20{i:02d}", owner_name="N/A", rating="4.5", reviews="10", website="",
                             address="1 Queen St W, Toronto, ON", search="Roofing | Toronto", btype="Roofing", hours="", status=st, notes="", enriched=False,
                             added_at=when, called_at=when if st != "none" else None, meeting_at=None, called_by=ids["gio"] if st != "none" else None, version=1, updated_at=F.now(), created_at=F.now()))
import leafline_backend as B
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
from PIL import Image
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)

def serve(api):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
    srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start(); return port

# two separate "devices": each has its own local profile file and its own engine
devA, devB = B.Api(profile_path=os.path.join(tempfile.mkdtemp(), "profile.json")), B.Api(profile_path=os.path.join(tempfile.mkdtemp(), "profile.json"))
for a in (devA, devB): a._ready.set(); assert a.sign_in("gio", "Gio123")["ok"]
pA, pB = serve(devA), serve(devB)
png = io.BytesIO(); Image.new("RGB", (800, 500), (30, 140, 90)).save(png, "PNG")

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{pA}/?t=tok&nointro"); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000)

    # account details: saved on device A, show up on device B
    pg.evaluate("async()=>{await go('account')}"); pg.wait_for_timeout(600)
    pg.fill("#aEmail", "gio@leaflineweb.com"); pg.fill("#aPhone", "(416) 555-0101"); pg.click("#aSave"); pg.wait_for_timeout(1500)
    check("email and phone saved on this device", devA.get_profile()["email"] == "gio@leaflineweb.com" and devA.get_profile()["phone"] == "(416) 555-0101")
    row = next((r for r in F.t["user_settings"] if r["user_id"] == ids["gio"]), None)
    check("...and to your private account row", bool(row) and row["data"]["account"]["email"] == "gio@leaflineweb.com")
    check("the note says it follows you to every device", "every device" in pg.inner_text("#dbNote"))
    pg.fill("#aEmail", "not-an-email"); pg.click("#aSave"); pg.wait_for_timeout(600)
    check("a malformed email is refused, the saved one stays", devA.get_profile()["email"] == "gio@leaflineweb.com")
    pg.fill("#aPhone", "(416) 555-0199"); pg.fill("#aEmail", "gio@leaflineweb.com"); pg.click("#xSave"); pg.wait_for_timeout(1500)
    check("'Save profile' also saves the account card (typed phone isn't lost)", devA.get_profile()["phone"] == "(416) 555-0199")
    pg2 = br.new_page(viewport={"width": 1440, "height": 900})
    pg2.goto(f"http://127.0.0.1:{pB}/?t=tok&nointro"); pg2.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000); pg2.wait_for_timeout(1500)
    check("another device picks up the email and phone", devB.get_profile()["email"] == "gio@leaflineweb.com" and devB.get_profile()["phone"] == "(416) 555-0199")
    pg2.close()

    # leaderboard: plain positions even when everyone is tied
    pg.evaluate("async()=>{await go('board');await new Promise(r=>setTimeout(r,1200));setP('lbMetric','money');drawRanks(true)}"); pg.wait_for_timeout(600)
    rk = pg.evaluate("()=>[...document.querySelectorAll('#lbBody .pod .rk, #lbBody .lbr .rk')].map(e=>e.textContent.trim())")
    check(f"positions count up instead of all reading #2 ({rk})", rk == ["#2", "#3", "#4"])

    # theme buttons centred, nothing spilling out
    r = pg.evaluate("""()=>{const t=document.querySelector('.top .lgt .thb'),tr=t.getBoundingClientRect(),d=t.querySelector('.ths').getBoundingClientRect();
      const s=document.querySelector('.side .foot .lgt').getBoundingClientRect(),f=document.querySelector('.side .foot').getBoundingClientRect();
      return {top:Math.abs((d.left+d.width/2)-(tr.left+tr.width/2)),side:Math.abs((s.left+s.width/2)-(f.left+f.width/2)),spill:[...document.querySelectorAll('.lgt .thb')].some(b=>b.scrollWidth>b.clientWidth+1)}}""")
    check("top-bar theme dot is centred in its button", r["top"] < 1)
    check("sidebar theme button is centred under 'Leafline Web Services'", r["side"] < 1)
    check("theme buttons don't spill their contents", not r["spill"])

    # Team cards: a long bio or a crowded name row never clips
    devA.set_profile_ext({"bio": "Akbar - 17 - Cold Caller - 6.5 Inches Greatest closer on the whole team and still going strong", "title": "CEO", "mood": "😴"})
    pg.evaluate("async()=>{const r=await api('boot');S.me=r.auth.me;await go('team')}"); pg.wait_for_timeout(1500)
    for w in (1440, 1100, 390):
        pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(500)
        bad = pg.evaluate("()=>[...document.querySelectorAll('.tm-p')].filter(c=>c.scrollWidth>c.clientWidth+1||c.getBoundingClientRect().right>innerWidth+1).length")
        check(f"no Team card clips at {w}px", bad == 0)
    pg.set_viewport_size({"width": 1440, "height": 900})

    # call notes: a real multi-line box
    pg.evaluate("async()=>{await go('called');await new Promise(r=>setTimeout(r,600));leadModal(S.called[0])}"); pg.wait_for_timeout(800)
    h = pg.evaluate("()=>document.querySelector('.ov.on #mNotes').getBoundingClientRect().height")
    check(f"call notes box has room for several lines ({round(h)}px)", h >= 100)
    pg.evaluate("document.querySelectorAll('.ov').forEach(o=>o.remove())")

    # dashboard banner: no small graphics; greeting, streak, callback queue, button, wider money box
    pg.evaluate("async()=>{await go('dash')}"); pg.wait_for_timeout(1800)
    d = pg.evaluate("""()=>{const b=document.querySelector('.banner.hero');return {ill:!!b.querySelector('.ill'),greet:b.querySelector('h2').textContent,stk:!!b.querySelector('.hz-stk .stk-track'),
      q:!!b.querySelector('.hz-q'),btn:!!b.querySelector('[data-go=find]'),money:Math.round(b.querySelector('.mtile').getBoundingClientRect().width)}}""")
    check("banner: the small graphics are gone", not d["ill"])
    check("banner keeps the greeting and the Find/Start button", "Gio" in d["greet"] and d["btn"])
    check("banner shows your streak and the callback queue", d["stk"] and d["q"])
    check(f"the money box is wider than before (>300px, got {d['money']})", d["money"] > 300)

    # notes: dark page switch is remembered
    pg.evaluate("async()=>{await go('notes');await new Promise(r=>setTimeout(r,500));await newNote('script')}"); pg.wait_for_timeout(800)
    pg.click("#edPaperT"); pg.wait_for_timeout(300)
    check("dark page switch turns the page dark and is remembered", pg.evaluate("()=>document.body.classList.contains('paper-dark')&&getP('notePaper')==='dark'"))
    check("reaction bar stays hidden on a private note", pg.evaluate("()=>document.getElementById('edRx').hidden"))
    pg.click("#edPaperT")

    # profile picture: crop and zoom, saved as a 512 px square
    pg.evaluate("async()=>{await go('account')}"); pg.wait_for_timeout(600)
    pg.set_input_files("#avFile", files=[{"name": "me.png", "mimeType": "image/png", "buffer": png.getvalue()}]); pg.wait_for_selector("#mdCrop")
    pg.wait_for_timeout(400); bx = pg.locator("#mdCrop").bounding_box()
    pg.mouse.move(bx["x"] + 120, bx["y"] + 120); pg.mouse.down(); pg.mouse.move(bx["x"] + 40, bx["y"] + 120, steps=5); pg.mouse.up()
    pg.locator("#mdZoom").fill("200"); pg.wait_for_timeout(200)
    pg.click(".ov.on [data-ok]"); pg.wait_for_timeout(2500)
    size = pg.evaluate("async()=>{const a=S.me.avatar;if(!a)return null;const i=new Image();i.src=a;await i.decode();return [i.naturalWidth,i.naturalHeight]}")
    check(f"cropped picture is saved as a square ({size})", size and size[0] == size[1] and size[0] >= 256)

    # lighter pictures and cached chats
    r = pg.evaluate("()=>{const d=S.me.avatar,a=imgTag(d,d);return {short:a.length<400,blob:a.includes('blob:'),same:a===imgTag(d,d)}}")
    check("pictures stored as text become one short shared link", r["short"] and r["blob"] and r["same"])
    # phones (iPhone): tap a business -> details pop up with Call; numbers dial; back closes it
    ip = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1")
    m = ip.new_page(); m.on("pageerror", lambda e: errs.append(str(e)))
    m.goto(f"http://127.0.0.1:{pA}/?t=tok&nointro#find"); m.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000); m.wait_for_timeout(800)
    check("phone: details are hidden until a business is tapped", m.evaluate("()=>getComputedStyle(document.getElementById('detail')).visibility")=="hidden")
    m.locator("#list .li").first.tap(); m.wait_for_timeout(600)
    r = m.evaluate("""()=>{const d=document.getElementById('detail').getBoundingClientRect(),c=document.querySelector('#detail .callb');
      return {open:document.body.classList.contains('dopen'),full:d.width>=innerWidth-1&&d.height>=innerHeight-1,href:c&&c.getAttribute('href'),shown:!!c&&c.getBoundingClientRect().width>0,marks:document.querySelectorAll('#detail [data-mark]').length}}""")
    check("phone: tapping a business opens its details full-screen", r["open"] and r["full"] and r["marks"] == 4)
    check(f"phone: a Call button dials the number ({r['href']})", r["shown"] and r["href"] == "tel:+14165552004")
    dp = m.evaluate("""()=>{const a=document.querySelector('#detail a.tel');let dp=null;const h=e=>{dp=e.defaultPrevented;e.preventDefault()};window.addEventListener('click',h);
      a.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));window.removeEventListener('click',h);return dp}""")
    check("phone: tapping the number itself is left to the phone to call", dp is False)
    m.tap("#dClose"); m.wait_for_timeout(500)
    check("phone: Back returns to the list", not m.evaluate("()=>document.body.classList.contains('dopen')"))
    m.locator("#list .li").first.tap(); m.wait_for_timeout(500); m.go_back(); m.wait_for_timeout(500)
    check("phone: swipe-back / browser back closes it too", not m.evaluate("()=>document.body.classList.contains('dopen')"))
    ip.close()
    dp = pg.evaluate("""async()=>{await go('find');await new Promise(r=>setTimeout(r,400));const a=document.querySelector('#detail a.tel');let dp=null;const h=e=>{dp=e.defaultPrevented;e.preventDefault()};window.addEventListener('click',h);
      a.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));window.removeEventListener('click',h);return [dp,getComputedStyle(document.querySelector('#detail .callb')).display]}""")
    check("computer: the number copies instead of dialling, and there's no Call button", dp == [True, "none"])
    check("no page errors", not errs or print(errs))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
