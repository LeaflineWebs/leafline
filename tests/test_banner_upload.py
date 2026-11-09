"""11.12.1: banner uploads. A file the server refuses (or cuts off) is reported as too big for the upload limit,
not as "you're offline"; being really offline still says offline. Big still banners are shrunk before uploading;
animated ones are kept as they are. PC engine and the website build."""
import os, sys, tempfile, threading, time, base64, json, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "employee") for n in ("omar", "gio")}
for p in F.t["profiles"]: p["must_change_password"] = False
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
PNG = b"\x89PNG\r\n\x1a\n"
def data_url(n): return "data:image/png;base64," + base64.b64encode(PNG + b"\0" * (n - len(PNG))).decode()

print("1. PC app")
api = B.Api(); api._ready.set(); assert api.sign_in("omar", "Omar123")["ok"]
t0 = time.time()
while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.3)
r = api.upload_media("banner", data_url(300_000))
check(f"a normal banner uploads ({r.get('error', '')[:80]})", r.get("ok") and any(ids["omar"] + "/banner-" in k for k in F.files))
r = api.upload_media("banner", data_url(9 * 1024 * 1024))
check(f"a file the server refuses as too large says so, not 'offline' ({r.get('error', '')[:60]})", not r["ok"] and "upload limit" in r["error"] and "offline" not in r["error"].lower())
F.cut_over = 2_000_000
r = api.upload_media("banner", data_url(3_000_000))
check("the server cutting the upload off is explained the same way", not r["ok"] and "upload limit" in r["error"])
F.cut_over = 0; F.down = True
r = api.upload_media("banner", data_url(300_000))
check("really offline still says offline", not r["ok"] and "offline" in r["error"].lower())
F.down = False
api._sync.stop.set()

print("2. website")
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1280, "height": 860}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", "gio"); pg.fill("#lgPass", "Gio123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=40000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    up = lambda n: pg.evaluate("async(u)=>await api('upload_media','banner',u,'')", data_url(n))
    r = up(9 * 1024 * 1024)
    check(f"website: a refused file says it's over the upload limit ({r.get('error', '')[:50]})", not r["ok"] and "upload limit" in r["error"])
    F.cut_over = 2_000_000; r = up(3_000_000); F.cut_over = 0
    check("website: a cut-off upload is explained too, not 'offline'", not r["ok"] and "upload limit" in r["error"] and "offline" not in r["error"].lower())
    # a big still photo is shrunk before upload; animated pictures are untouched
    r = pg.evaluate("""async()=>{const W=6000,H=1500,c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d'),g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#1d4130');g.addColorStop(1,'#d9a441');x.fillStyle=g;x.fillRect(0,0,W,H);
        const d=x.getImageData(0,0,W,H),a=d.data;for(let i=0;i<a.length;i+=4){const n=(Math.random()-.5)*40;a[i]+=n;a[i+1]+=n;a[i+2]+=n}x.putImageData(d,0,0);
        const big=await new Promise(r=>c.toBlob(b=>r(new File([b],'big.png',{type:'image/png'})),'image/png'));
        const out=await shrinkBanner(big),im=await createImageBitmap(out);
        const gif=new File([new Uint8Array([71,73,70,56,57,97,1,0,1,0,0,0,0])],'a.gif',{type:'image/gif'});
        const apng=new File([new Uint8Array([137,80,78,71,13,10,26,10,0,0,0,8,97,99,84,76,0,0,0,2])],'a.png',{type:'image/png'});
        return {before:big.size,after:out.size,w:im.width,h:im.height,type:out.type,gif:(await shrinkBanner(gif))===gif,apng:await isAnimatedFile(apng),png:await isAnimatedFile(big)}}""")
    check(f"a big still banner is shrunk to 3000px wide before upload ({r['before']//1024} KB -> {r['after']//1024} KB)", r["w"] == 3000 and r["h"] == 750 and r["after"] < r["before"] / 3)
    check("animated GIFs and animated PNGs are left exactly as they are", r["gif"] and r["apng"] and not r["png"])
    # the whole dialog: pick a big photo, Save -> a small file reaches the server
    F.cut_over = 2_000_000; before = set(F.files)
    pg.evaluate("""async()=>{const W=5000,H=1250,c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d'),g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#1d4130');g.addColorStop(1,'#d9a441');x.fillStyle=g;x.fillRect(0,0,W,H);
        const d=x.getImageData(0,0,W,H),a=d.data;for(let i=0;i<a.length;i+=4){const n=(Math.random()-.5)*40;a[i]+=n;a[i+1]+=n;a[i+2]+=n}x.putImageData(d,0,0);
        const f=await new Promise(r=>c.toBlob(b=>r(new File([b],'photo.png',{type:'image/png'})),'image/png'));window._sz=f.size;await go('account');mediaDialog('banner',f)}""")
    pg.wait_for_selector(".ov.on [data-ok]"); pg.click(".ov.on [data-ok]")
    pg.wait_for_function("!document.querySelector('.ov.on')", timeout=30000); pg.wait_for_timeout(500)
    new = [k for k in F.files if k not in before]
    sz = pg.evaluate("()=>window._sz")
    check(f"a {sz // 1024} KB photo uploads even under a 2 MB server limit, because it is shrunk first", len(new) == 1 and len(F.files[new[0]][0]) < 2_000_000 and sz > 2_000_000)
    F.cut_over = 0
    check("no page errors", not errs or print(errs))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
