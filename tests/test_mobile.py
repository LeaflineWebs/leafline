"""Phones (11.8.2): the real WEBSITE build on iPhone-sized touch screens, the way the team uses it.
Find Leads scrolls as one page, every lead has Call, calling works on the website, after a call the business opens
at its result buttons, ticking several shows a bar to mark them together, the bottom bar sits on the bottom edge,
the More menu never cuts a name off, and the chat can't be dragged sideways."""
import os, sys, tempfile, threading, json, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "employee") for n in ("gio", "tim")}
for p in F.t["profiles"]: p["must_change_password"] = False
for i in range(1, 19):
    F.t["leads"].append(dict(id=f"m{i}", name=f"Roofing Pros {i}", phone=f"(519) 555-01{i:02d}", owner_name="N/A", email="N/A", rating="4.5", reviews=str(200 - i),
                             website="N/A", address="1 Main St, Kitchener, ON", search="roofers | Kitchener", btype="Roofing", hours="", status="none", notes="",
                             enriched=False, added_at="2026-11-07T14:00:00+00:00", called_at=None, meeting_at=None, version=1, updated_at=F.now(), created_at=F.now(),
                             phone_key=f"51955501{i:02d}"))
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
import leafline_backend as B
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
CLICK = """(sel)=>{const a=document.querySelector(sel);let dp=null;const h=e=>{dp=e.defaultPrevented;e.preventDefault()};window.addEventListener('click',h);
  a.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));window.removeEventListener('click',h);return dp}"""

def phone(br, w, h):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=UA)
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", "gio"); pg.fill("#lgPass", "Gio123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=40000)
    return ctx, pg, errs

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    ctx, pg, errs = phone(br, 390, 844)
    check("this is the website build (the same one iPhones load)", pg.evaluate("()=>document.documentElement.classList.contains('web')&&!!window.LF_API"))
    check("on the website, a phone can place calls", pg.evaluate("()=>canCall()"))
    pg.evaluate("async()=>{await go('find');await new Promise(r=>setTimeout(r,900))}")
    r = pg.evaluate("""()=>{const pg=document.getElementById('pg-find'),l=document.getElementById('list');
      return {page:pg.scrollHeight>pg.clientHeight+50,box:l.scrollHeight>l.clientHeight+2,seen:[...document.querySelectorAll('#list .li')].filter(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight-80}).length,
       banner:getComputedStyle(document.querySelector('.fcard')).display,exp:getComputedStyle(document.getElementById('fExport')).display}}""")
    check("Find Leads scrolls as one page; the list isn't a small box with its own scroll", r["page"] and not r["box"])
    check(f"at least 4 whole leads fit on screen at once (got {r['seen']})", r["seen"] >= 4)
    check("the desktop-only search banner and Export are hidden on phones", r["banner"] == "none" and r["exp"] == "none")
    pg.evaluate("()=>{const p=document.getElementById('pg-find');p.style.scrollBehavior='auto';p.scrollTop=p.scrollHeight}"); pg.wait_for_timeout(300)
    check("scrolling all the way shows the last lead clear of the page bar", pg.evaluate("()=>{const a=[...document.querySelectorAll('#list .li')],r=a[a.length-1].getBoundingClientRect();return r.bottom<=document.querySelector('.fpill').getBoundingClientRect().top}"))
    pg.evaluate("()=>{const p=document.getElementById('pg-find');p.scrollTop=0;p.style.scrollBehavior=''}")
    c = pg.evaluate("""()=>[...document.querySelectorAll('#list .li')].map(li=>{const a=li.querySelector('.lcall'),r=a.getBoundingClientRect();return [a.getAttribute('href'),Math.round(r.width),Math.round(r.height)]})""")
    check(f"every lead has a Call button at least 44px ({c[0]})", len(c) == 18 and all(h.startswith("tel:+1519555") and w >= 44 and hh >= 44 for h, w, hh in c))
    check("tapping Call is left to the phone to dial (not blocked)", pg.evaluate(CLICK, "#list .li .lcall") is False)
    check("tapping Call doesn't open the business", not pg.evaluate("()=>document.body.classList.contains('dopen')"))
    first = pg.evaluate("()=>document.querySelector('#list .li').dataset.id")
    # the call happens (app goes to the background) and you come back
    pg.evaluate("()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))}")
    pg.evaluate("()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))}")
    pg.wait_for_timeout(1600)
    r = pg.evaluate("()=>({open:document.body.classList.contains('dopen'),id:S.active,title:document.querySelector('#detail h2').textContent,toast:document.getElementById('tMsg').textContent,mark:!!document.querySelector('#detail .mark')})")
    check("coming back from the call opens that business at its result buttons", r["open"] and r["id"] == first and r["mark"] and "How did the call" in r["toast"])
    cover = pg.evaluate("()=>{const t=document.getElementById('toast').getBoundingClientRect(),m=document.querySelector('#detail .mark').getBoundingClientRect();return !(t.bottom<=m.top||t.top>=m.bottom)}")
    check("the 'How did the call go?' message doesn't cover the result buttons", not cover)
    pg.tap("#detail [data-mark=orange]"); pg.wait_for_timeout(1500)
    check("one more tap logs the result and returns to the list", not pg.evaluate("()=>document.body.classList.contains('dopen')"))
    check("...and the business left the call list", pg.evaluate(f"()=>!document.querySelector('#list .li[data-id=\"{first}\"]')"))
    # a call that was cancelled (app never left) doesn't open anything
    pg.evaluate(CLICK, "#list .li .lcall"); pg.evaluate("()=>document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(1000)
    check("a cancelled call doesn't pop anything open", not pg.evaluate("()=>document.body.classList.contains('dopen')"))
    # tick two, mark them together
    pg.locator("#list .li .chk").nth(0).tap(); pg.locator("#list .li .chk").nth(1).tap(); pg.wait_for_timeout(500)
    r = pg.evaluate("()=>{const b=document.getElementById('selBar'),r=b.getBoundingClientRect();return {on:b.classList.contains('on'),txt:b.querySelector('span').textContent,above:r.bottom<=document.querySelector('.fpill').getBoundingClientRect().top+1}}")
    check("ticking businesses shows a bar with how many, above the page bar", r["on"] and r["txt"] == "2 selected" and r["above"])
    pg.tap("#selBar [data-sm]"); pg.wait_for_timeout(700)
    check("'Mark as…' opens the result buttons for both", pg.evaluate("()=>document.body.classList.contains('dopen')&&/Mark 2 selected/.test(document.getElementById('markT').textContent)"))
    n0 = pg.evaluate("()=>document.querySelectorAll('#list .li').length")
    pg.tap("#detail [data-mark=red]"); pg.wait_for_timeout(1500)
    check("both are marked and leave the list; the bar goes away", pg.evaluate("()=>document.querySelectorAll('#list .li').length") == n0 - 2 and not pg.evaluate("()=>document.getElementById('selBar').classList.contains('on')"))
    # page bar flush with the bottom edge, full width
    r = pg.evaluate("()=>{const r=document.querySelector('.fpill').getBoundingClientRect();return [r.left,r.right,r.bottom,innerWidth,innerHeight]}")
    check(f"the page bar is full width and sits on the bottom edge ({r})", r[0] <= 0.5 and r[1] >= r[3] - 0.5 and abs(r[2] - r[4]) <= 0.5)
    check("the page bar leaves room for the iPhone home bar", "calc(2px + env(safe-area-inset-bottom))" in B.UI_HTML)
    # chat: up and down only
    check("chat scrolls up and down only (can't be dragged sideways)", ".mx-scroll{flex:1;overflow-y:auto;overflow-x:hidden" in B.UI_HTML and "touch-action:pan-y pinch-zoom" in B.UI_HTML)
    check("no page errors", not errs or print(errs))
    ctx.close()
    # More menu: no name cut off, on the smallest to the largest current iPhones
    for w, h in ((375, 812), (390, 844), (430, 932)):
        ctx, pg, errs = phone(br, w, h)
        pg.evaluate("()=>document.getElementById('fmore').click()"); pg.wait_for_timeout(700)
        cut = pg.evaluate("()=>[...document.querySelectorAll('#msheet .sg button')].filter(b=>b.scrollWidth>b.clientWidth+1||[...b.querySelectorAll('span')].some(s=>s.offsetWidth&&s.scrollWidth>s.offsetWidth+1)).map(b=>b.innerText)")
        check(f"{w}px: no name in the More menu is cut off", not cut or print(cut))
        pg.evaluate("async()=>{document.getElementById('msheet').classList.remove('on','show');await go('find');await new Promise(r=>setTimeout(r,700))}")
        wide = pg.evaluate("()=>document.documentElement.scrollWidth>innerWidth+1||document.getElementById('pg-find').scrollWidth>innerWidth+1")
        check(f"{w}px: Find Leads never scrolls sideways", not wide)
        ctx.close()
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
