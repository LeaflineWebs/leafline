"""11.7 polish pass: company logo top-left for everyone, no class clash in the header, the floating page bar fits,
skeleton loading, list motion, and reduced motion respected everywhere."""
import os, sys, tempfile, threading, time
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
NAMES = ("gio", "james", "akbar", "omar", "jaylen", "tim")
ids = {n: F.add_user(n, n.title() + "123", "admin" if n in ("james", "omar", "akbar") else "employee") for n in NAMES}
for p in F.t["profiles"]: p["must_change_password"] = False
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
import requests
page = requests.get(f"http://127.0.0.1:{port}/?t=tok").text
check("desktop page drops the missing font files instead of requesting them", "fonts/Inter" not in page and "__FONT_" not in page)
check("desktop page has its own tab icon", 'rel="icon" id="appIcon"' in page)

LOOK = r"""()=>{const vis=e=>!!e&&e.getBoundingClientRect().width>0;const logo=[...document.querySelectorAll('#sideBrand .bmk svg,#mBrand svg')].filter(vis);
  const av=[document.getElementById('sideAv'),document.getElementById('mAv')].filter(vis)[0];
  return {logos:logo.length,leaf:logo.length?logo[0].querySelector('path').getAttribute('d').slice(0,5):'',logoTopLeft:logo.length?logo[0].getBoundingClientRect().left<innerWidth/2&&logo[0].getBoundingClientRect().top<120:false,
   avatar:av?av.textContent.trim():'',avInsideLogo:logo.length&&!!logo[0].closest('.bmk').querySelector('.in-av,img'),mavShown:vis(document.getElementById('mAvBtn'))}}"""
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    for W in (1440, 390):
        ctx = br.new_context(viewport={"width": W, "height": 900}, is_mobile=W < 800, has_touch=W < 800); pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
        pg.goto(f"http://127.0.0.1:{port}/?t=tok&nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=20000)
        for n in NAMES:
            pg.fill("#lgUser", n); pg.fill("#lgPass", n.title() + "123"); pg.press("#lgPass", "Enter")
            pg.wait_for_function(f"typeof S!=='undefined'&&S.ready&&S.me&&S.me.username==='{n}'", timeout=60000); pg.wait_for_timeout(500)
            r = pg.evaluate(LOOK)
            check(f"{W}px {n}: the Leafline logo is top-left and is the leaf, not a picture",
                  r["logos"] == 1 and r["leaf"] == "M51 9" and r["logoTopLeft"] and not r["avInsideLogo"])
            check(f"{W}px {n}: their own picture/initial is shown separately", r["avatar"] == n[0].upper())
            if W > 860: check(f"{W}px {n}: the phone picture button stays hidden on computers", not r["mavShown"])
            pg.evaluate("api('sign_out')"); pg.reload(); pg.wait_for_selector("#lgUser", state="visible", timeout=20000)
        check(f"{W}px: no page errors while switching accounts", not errs or print(errs))
        ctx.close()

    # floating page bar fits inside the content area at every desktop width (an admin has the most buttons),
    # also with the script panel open, and it stays centred
    api.sign_out()
    pg = br.new_page(viewport={"width": 1024, "height": 860})
    pg.goto(f"http://127.0.0.1:{port}/?t=tok&nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=20000)
    pg.fill("#lgUser", "james"); pg.fill("#lgPass", "James123"); pg.press("#lgPass", "Enter")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000)
    FIT = "()=>{const r=document.querySelector('#fnav').getBoundingClientRect(),m=document.querySelector('#main').getBoundingClientRect();return r.left>=m.left-1&&r.right<=m.right+1}"
    CEN = "()=>{const r=document.querySelector('#fnav').getBoundingClientRect(),m=document.querySelector('#main').getBoundingClientRect(),d=document.querySelector('#main').classList.contains('hasdock')?+getComputedStyle(document.querySelector('#main')).getPropertyValue('--dockw').replace('px',''):0;return Math.abs((r.left+r.right)/2-(m.left+m.right-d)/2)<3}"
    for w in (1024, 1180, 1280, 1440, 1920):
        pg.set_viewport_size({"width": w, "height": 860}); pg.wait_for_timeout(700)
        check(f"page bar fits inside the content area at {w}px", pg.evaluate(FIT))
        check(f"page bar is centred in the content area at {w}px", pg.evaluate(CEN))
    pg.set_viewport_size({"width": 1440, "height": 860})

    # skeletons and list motion
    check("Admin shows a skeleton (not 'Loading...') while it waits", "Loading the admin" not in B.UI_HTML and pg.evaluate("()=>skel(SKEL.admin).includes('class=\"skl\"')"))
    pg.evaluate("()=>go('team')"); pg.wait_for_timeout(120)
    moving = pg.evaluate("()=>document.getAnimations().filter(a=>a.effect&&a.effect.target&&a.effect.target.closest&&a.effect.target.closest('.tm-tiles,.tm-people')).length")
    check("opening Team eases its tiles and cards in", moving >= 3)
    pg.wait_for_timeout(2600)
    pg.evaluate("()=>renderTeam()"); pg.wait_for_timeout(200)
    still = pg.evaluate("()=>document.getAnimations().filter(a=>a.effect&&a.effect.target&&a.effect.target.closest&&a.effect.target.closest('.tm-people')).length")
    check("a background refresh later on does not replay the entrance", still == 0)
    pg.close()

    # reduced motion: nothing scripted moves
    api.sign_out()
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce"); pg = ctx.new_page()
    pg.goto(f"http://127.0.0.1:{port}/?t=tok&nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=20000)
    pg.fill("#lgUser", "gio"); pg.fill("#lgPass", "Gio123"); pg.press("#lgPass", "Enter")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000)
    long = pg.evaluate("""async()=>{let n=0;const seen=new Set();let run=true;const t=()=>{document.getAnimations().forEach(a=>{if(seen.has(a))return;seen.add(a);
       const d=a.effect&&a.effect.getComputedTiming?a.effect.getComputedTiming().duration:0;if(d>20&&a.constructor.name==='Animation')n++});if(run)requestAnimationFrame(t)};t();
       for(const p of ['team','board','profits','msgs'])await go(p);await new Promise(r=>setTimeout(r,800));run=false;return n}""")
    check("with 'reduce motion' on, no scripted animation runs (page title included)", long == 0)
    ctx.close()
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
