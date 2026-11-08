"""11.9: pictures keep their shape at every window size, the What's new window after updates, banners up to 100 MB."""
import os, sys, tempfile, threading
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
import json, re
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "employee") for n in ("gio", "tim")}
for p in F.t["profiles"]: p["must_change_password"] = False
import leafline_backend as B
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)

ver = json.load(open(os.path.join(HERE, "..", "package.json"), encoding="utf-8"))["version"]
first = re.search(r'const PATCH_NOTES=\[\s*\{v:"([\d.]+)"', B.UI_HTML)
check(f"the newest notes are for this version ({ver})", first and first.group(1) == ver)
api = B.Api(); api._ready.set(); assert api.sign_in("gio", "Gio123")["ok"]
srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
SHAPES = """()=>[...document.querySelectorAll('.ring,.in-av,.tav,.bmk,.rb,.ths')].filter(e=>{const r=e.getBoundingClientRect();return r.width>8&&r.height>0&&Math.abs(r.width-r.height)>1.5})
  .map(e=>(e.id||e.className).split(' ')[0]+' '+Math.round(e.getBoundingClientRect().width)+'x'+Math.round(e.getBoundingClientRect().height))"""

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    for w, h in ((1440, 900), (1366, 620), (1280, 700), (1100, 540), (900, 500)):
        pg = br.new_page(viewport={"width": w, "height": h})
        pg.goto(f"http://127.0.0.1:{port}/?t=tok&nointro"); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000); pg.wait_for_timeout(900)
        bad = pg.evaluate(SHAPES)
        check(f"{w}x{h}: every picture, logo and round button keeps its shape", not bad or print(bad))
        top = pg.evaluate("()=>{const t=document.querySelector('.top');return t.scrollWidth>t.clientWidth+1}")
        check(f"{w}x{h}: the top bar fits", not top)
        pg.close()

    # What's new: once after an update, then never again on this device until the next one
    ctx = br.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?t=tok&nointro&notes"); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000)
    pg.wait_for_selector(".ov.on .pn", timeout=15000)
    t = pg.inner_text(".ov.on .pn")
    check(f"after an update, What's new opens by itself and names this version", f"What's new in Leafline {ver}".lower() in t.lower() and "100 MB" in t)
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(600)
    check("'Got it' closes it", not pg.evaluate("()=>!!document.querySelector('.ov.on')"))
    pg.reload(); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000); pg.wait_for_timeout(3500)
    check("it doesn't come back on the next start", not pg.evaluate("()=>!!document.querySelector('.ov.on .pn')"))
    pg.evaluate("()=>localStorage.setItem('lf_notes_seen','11.8.1')"); pg.reload(); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000)
    pg.wait_for_selector(".ov.on .pn", timeout=15000)
    vers = pg.evaluate("()=>[...document.querySelectorAll('.ov.on .pn details summary b')].map(b=>b.textContent)")
    check(f"after skipping updates, it lists every one you missed ({vers})", vers == ["11.8.3", "11.8.2"])
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(500)
    pg.evaluate("async()=>{await go('account')}"); pg.wait_for_timeout(700); pg.click("#pnBtn"); pg.wait_for_selector(".ov.on .pn")
    n = pg.evaluate("()=>document.querySelectorAll('.ov.on .pn details').length")
    check(f"Settings › What's new shows the whole history ({n + 1} updates)", n >= 8)
    pg.click(".ov.on [data-x]"); pg.wait_for_timeout(400)
    # banners up to 100 MB, pictures 8 MB (the dialog checks before uploading)
    big = pg.evaluate("""async()=>{const mk=n=>new File([new Uint8Array(n)],'x.gif',{type:'image/gif'});const msgs=[];const t=window.toast;window.toast=(m)=>msgs.push(m);
      mediaDialog('avatar',mk(9*1024*1024));mediaDialog('banner',mk(101*1024*1024));const ov=document.querySelectorAll('.ov.on').length;window.toast=t;return {msgs,ov}}""")
    check("a 9 MB profile picture is refused (limit 8 MB)", any("limit is 8 MB" in m for m in big["msgs"]))
    check("a 101 MB banner is refused (limit 100 MB)", any("limit is 100 MB" in m for m in big["msgs"]))
    ok9 = pg.evaluate("""async()=>{const f=new File([new Uint8Array(9*1024*1024)],'b.gif',{type:'image/gif'});mediaDialog('banner',f);await new Promise(r=>setTimeout(r,400));
      const o=!!document.querySelector('.ov.on .mprev');document.querySelectorAll('.ov').forEach(x=>x.remove());return o}""")
    check("a 9 MB banner is accepted (opens the preview)", ok9)
    check("no page errors", not errs or print(errs))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
