"""11.17: liquid glass. Turned on and off with the switch in Settings > Appearance. Checks the real optics, not just
the look: per-shape SVG filters (sRGB, three colour channels, normal maps at each surface's exact size with a flat
middle), the 900 x 900 limit, the card budget, that the rim really bends what is behind it while the middle does not
(stripes behind each surface, bending on vs off), the spring on switch thumbs, every theme, PC and phone sizes, and
that switching off removes everything. Runs the real WEBSITE build in Chromium against the fake shared database."""
import os, sys, tempfile, threading, http.server, functools, uuid, io
from datetime import datetime, timedelta, timezone
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
OUT = os.environ.get("LEAFLINE_SHOTS") or tempfile.mkdtemp()
from fake_supabase import Fake
from PIL import Image, ImageChops
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "employee") for n in ("gio", "kyle")}
for p in F.t["profiles"]: p["must_change_password"] = False
now = datetime.now(timezone.utc)
for d in range(0, 8):
    for i in range(6):
        F.t["call_log"].append(dict(id=str(uuid.uuid4()), client_op_id=str(uuid.uuid4()), lead_id=None, employee_id=ids["kyle"], phone="5195550101",
            started_at=(now - timedelta(days=d, minutes=i)).isoformat(), outcome="meeting_booked" if i == 0 else "no_answer", notes="", source="app", credited_to=None, created_at=now.isoformat()))
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
from playwright.sync_api import sync_playwright
ok = fail = 0
def chk(name, c, extra=""):
    global ok, fail
    if c: ok += 1; print("  PASS", name)
    else: fail += 1; print("  FAIL", name, extra)
errs = []
THEMES = ["forest", "emerald", "midnight", "ruby", "amber", "gold", "lime", "ocean", "indigo", "violet", "obsidian"]
def shot(pg): return Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
STRIPES = "repeating-linear-gradient(90deg,#fff 0 3px,transparent 3px 22px),repeating-linear-gradient(0deg,rgba(255,80,80,.95) 0 3px,transparent 3px 22px),#123"
def refr_diff(pg, sel, behind=".main"):
    """Puts stripes behind the surface, then compares bending on vs off (same blur both times).
    Returns (changed share of the outer rim band, changed share of the middle)."""
    box = pg.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]}""", sel)
    if not box: return None
    if behind.startswith("under:"):   # a striped sheet right under the surface (same stacking level, one below)
        pg.evaluate("""([s,st,z])=>{const e=document.querySelector(s),r=e.getBoundingClientRect(),d=document.createElement('div');d.id='zzStripes';
            d.style.cssText=`position:fixed;left:${r.left-30}px;top:${r.top-30}px;width:${r.width+60}px;height:${r.height+60}px;z-index:${z};pointer-events:none;background:${st}`;(e.closest('.app')||document.body).appendChild(d)}""", [sel, STRIPES, int(behind[6:])])
    else:
        pg.evaluate("([b,st])=>{const e=document.querySelector(b);e.dataset.bg=e.style.background;e.style.setProperty('background',st,'important')}", [behind, STRIPES])
    pg.wait_for_timeout(300)
    a = shot(pg)
    pg.evaluate("""()=>{const B={'frosted-pill':8,'thick-lens':12,'liquid-mercury':4,'subtle-pane':20};for(const r of LG._L.recs.values()){if(r.att){const el=r.el;el.dataset.keep=el.style.getPropertyValue(r.p==='liquid-mercury'?'--lgf':'backdrop-filter');
        const nb=el.dataset.keep.replace(/url\\([^)]*\\)/,'blur('+B[r.p]+'px)');if(r.p==='liquid-mercury')el.style.setProperty('--lgf',nb);else el.style.setProperty('backdrop-filter',nb,'important')}}}""")
    pg.wait_for_timeout(300); b = shot(pg)
    pg.evaluate("""()=>{for(const r of LG._L.recs.values()){if(r.att){const el=r.el;if(r.p==='liquid-mercury')el.style.setProperty('--lgf',el.dataset.keep);else el.style.setProperty('backdrop-filter',el.dataset.keep,'important');delete el.dataset.keep}}}""")
    if behind.startswith("under:"): pg.evaluate("()=>document.getElementById('zzStripes').remove()")
    else: pg.evaluate("(b)=>{const e=document.querySelector(b);e.style.background=e.dataset.bg||'';delete e.dataset.bg}", behind)
    pg.wait_for_timeout(150)
    x0, y0, x1, y1 = [int(v) for v in box]
    d = ImageChops.difference(a.crop((x0, y0, x1, y1)), b.crop((x0, y0, x1, y1))).convert("L").point(lambda v: 255 if v > 24 else 0)
    w, h = d.size; band = max(6, min(14, min(w, h) // 4))
    px = d.load(); rim = mid = nr = nm = 0
    for y in range(h):
        for x in range(w):
            e = min(x, y, w - 1 - x, h - 1 - y)
            if e < 2: continue
            if e < band: nr += 1; rim += px[x, y] > 0
            elif e >= band + 8: nm += 1; mid += px[x, y] > 0
    return round(rim / max(1, nr), 3), round(mid / max(1, nm), 3)
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    for phone in (False, True):
        o = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=1) if phone else dict(viewport={"width": 1440, "height": 900})
        ctx = br.new_context(**o); pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
        pg.fill("#lgUser", "gio"); pg.fill("#lgPass", "Gio123"); pg.click("#lgGo")
        pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000); pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
        tag = "phone" if phone else "desk"
        # switch it on from Settings > Appearance
        pg.evaluate("async()=>{await go('account',true)}"); pg.wait_for_selector("#lgTgl"); pg.wait_for_timeout(600)
        chk(f"[{tag}] switch is in the Appearance card", pg.evaluate("()=>!!document.querySelector('#themeCard #lgTgl')"))
        chk(f"[{tag}] glass is off to start", pg.evaluate("()=>!document.documentElement.classList.contains('lf-glass')&&$('#lgTgl').getAttribute('aria-checked')==='false'"))
        pg.click("#lgTgl"); pg.wait_for_timeout(900)
        chk(f"[{tag}] switch turns glass on", pg.evaluate("()=>document.documentElement.classList.contains('lf-glass')&&$('#lgTgl').getAttribute('aria-checked')==='true'&&localStorage.getItem('lf_glass')==='1'&&S.prefs.glass===true"))
        st = pg.evaluate("()=>{const L=LG._L;return {opt:L.opt,recs:L.recs.size,att:[...L.recs.values()].filter(r=>r.att).map(r=>r.p),filters:L.filters.size}}")
        print("  ", st["recs"], "surfaces,", len(st["att"]), "bending,", st["filters"], "filters, optical:", st["opt"])
        chk(f"[{tag}] optical refraction available in Chromium", st["opt"])
        chk(f"[{tag}] surfaces are bending", len(st["att"]) >= 4, sorted(set(st["att"])))
        chk(f"[{tag}] cards stay within the budget", st["att"].count("subtle-pane") <= (6 if phone else 14))
        chk(f"[{tag}] every filter uses sRGB", pg.evaluate("()=>[...document.querySelectorAll('#lgDefs filter')].every(f=>f.getAttribute('color-interpolation-filters')==='sRGB')"))
        chk(f"[{tag}] three colour channels per filter", pg.evaluate("()=>[...document.querySelectorAll('#lgDefs filter')].every(f=>f.querySelectorAll('feDisplacementMap').length===3)"))
        chk(f"[{tag}] maps match each surface's size", pg.evaluate("""()=>[...LG._L.recs.values()].filter(r=>r.att&&r.p!=='liquid-mercury').every(r=>{const f=document.getElementById(LG._L.filters.get(r.key).id).querySelector('feImage');return +f.getAttribute('width')===r.el.offsetWidth&&+f.getAttribute('height')===r.el.offsetHeight})"""))
        chk(f"[{tag}] nothing over 900x900 bends", pg.evaluate("()=>[...LG._L.recs.values()].filter(r=>r.att).every(r=>{const w=r.el.offsetWidth,h=r.el.offsetHeight;return !(w>900&&h>900)&&w*h<=810000})"))
        chk(f"[{tag}] main panel never bends", pg.evaluate("()=>!document.querySelector('.main').style.backdropFilter"))
        # the centre of the normal map is flat (128,128,0)
        flat = pg.evaluate("""async()=>{const r=[...LG._L.recs.values()].find(r=>r.att&&r.p==='subtle-pane');if(!r)return null;const im=document.getElementById(LG._L.filters.get(r.key).id).querySelector('feImage');
            const i=new Image();i.src=im.getAttribute('href');await i.decode();const c=document.createElement('canvas');c.width=i.width;c.height=i.height;const x=c.getContext('2d');x.drawImage(i,0,0);
            const px=(a,b)=>[...x.getImageData(a,b,1,1).data].slice(0,3);return {mid:px(i.width>>1,i.height>>1),inner:px(30,30),edge:px(i.width-1,i.height>>1),top:px(i.width>>1,0)}}""")
        chk(f"[{tag}] map centre is flat and the rim leans out", flat and flat["mid"] == [128, 128, 0] and flat["inner"] == [128, 128, 0] and flat["edge"][0] > 200 and flat["top"][1] < 60, flat)
        pg.screenshot(path=os.path.join(OUT, f"{tag}_settings.png"))
        for th in THEMES:
            pg.evaluate(f"()=>setTheme('{th}',false,false)")
            tint = pg.evaluate("()=>{const e=document.querySelector('.fpill');return [getComputedStyle(e).backgroundImage,getComputedStyle(document.documentElement).getPropertyValue('--card').trim()]}")
            chk(f"[{tag}] {th}: the glass is tinted from the theme", tint[1] and "color-mix" not in tint[0] and tint[0].count("gradient") >= 3)
            for page in (["dash", "team", "board", "account"] if not phone else ["dash", "team"]):
                pg.evaluate(f"async()=>{{await go('{page}',true)}}"); pg.wait_for_timeout(1300)
                pg.screenshot(path=os.path.join(OUT, f"{tag}_{th}_{page}.png"))
        pg.evaluate("()=>setTheme('forest',false,false)")
        pg.evaluate("async()=>{await go('dash',true)}"); pg.wait_for_timeout(1200)
        pg.evaluate("()=>{const r=[...LG._L.recs.values()].find(r=>r.att&&r.el.matches('.page.on .card,.page.on .stat,.page.on .banner'));if(r)r.el.dataset.zz='1'}")
        for sel, nm, bh in ([(".fpill", "bottom bar", "under:29"), ("[data-zz]", "a card", ".main")] + ([(".side", "sidebar", "body"), ("#bellBtn", "a round button", ".main")] if not phone else [])):
            r = refr_diff(pg, sel, bh)
            chk(f"[{tag}] {nm} really bends what's behind it at the rim, not in the middle", r and r[0] > .04 and r[1] < r[0] / 3, r)
        # a dialog over the page
        pg.evaluate("()=>alertBox('Glass check','This dialog is thick-lens glass over the page.')"); pg.wait_for_selector(".ov.on .dlg[data-lgp]"); pg.wait_for_timeout(700)
        chk(f"[{tag}] dialogs are thick-lens glass", pg.evaluate("()=>document.querySelector('.ov.on .dlg').dataset.lgp==='thick-lens'&&!!LG._L.recs.get(document.querySelector('.ov.on .dlg')).att"))
        r = refr_diff(pg, ".ov.on .dlg", "under:69"); chk(f"[{tag}] the dialog bends the page behind it at the rim", r and r[0] > .04 and r[1] < r[0] / 3, r)
        pg.screenshot(path=os.path.join(OUT, f"{tag}_dialog.png"))
        pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())"); pg.wait_for_timeout(200)
        chk(f"[{tag}] closed dialogs are let go", pg.evaluate("()=>[...LG._L.recs.keys()].every(e=>e.isConnected)"))
        # team page redraws every 8 s: filters are reused, not piled up
        pg.evaluate("async()=>{await go('team',true)}"); pg.wait_for_timeout(1500); n1 = pg.evaluate("()=>document.querySelectorAll('#lgDefs filter').length")
        pg.wait_for_timeout(9000); n2 = pg.evaluate("()=>document.querySelectorAll('#lgDefs filter').length")
        chk(f"[{tag}] Team redraws reuse the same filters", n2 <= n1 + 1 and n2 <= 48, (n1, n2))
        # switch thumb: spring
        pg.evaluate("async()=>{await go('account',true)}"); pg.wait_for_selector("#lgTgl"); pg.wait_for_timeout(700)
        chk(f"[{tag}] the switch thumb is liquid glass", pg.evaluate("()=>{const r=LG._L.recs.get($('#lgTgl'));return !!(r&&r.p==='liquid-mercury'&&r.att)}"))
        r = refr_diff(pg, "#lgTgl", "#lgTgl"); chk(f"[{tag}] the thumb bends the track under it", r and r[0] > .02, r)
        pg.screenshot(path=os.path.join(OUT, f"{tag}_switch_on.png"), clip=pg.evaluate("()=>{const r=$('#themeCard .lfg-row').getBoundingClientRect();return {x:r.left,y:r.top,width:r.width,height:r.height}}"))
        # turn it off: everything goes back
        xs = pg.evaluate("""async()=>{const out=[];const t=$('#lgTgl');t.click();for(let i=0;i<40;i++){await new Promise(r=>requestAnimationFrame(r));out.push(getComputedStyle(t,'::after').transform)}return out}""")
        chk(f"[{tag}] switching off turns glass off", pg.evaluate("()=>!document.documentElement.classList.contains('lf-glass')&&localStorage.getItem('lf_glass')==='0'&&!document.querySelector('[data-lgp]')&&!document.querySelector('#lgDefs filter')&&S.prefs.glass===false"))
        pg.click("#lgTgl"); pg.wait_for_timeout(50)
        xs = pg.evaluate("""async()=>{const out=[];const t=$('#lgTgl');t.classList.toggle('on');for(let i=0;i<50;i++){await new Promise(r=>requestAnimationFrame(r));const v=t.style.getPropertyValue('--tx');out.push(v?parseFloat(v):null)}return out}""")
        vals = [v for v in xs if v is not None]
        chk(f"[{tag}] switch thumb moves on a spring (overshoots a little, then settles)", vals and min(vals) < -0.3 and xs[-1] is None, [round(v, 1) for v in vals[:14]])
        pg.evaluate("()=>$('#lgTgl').classList.toggle('on')"); pg.wait_for_timeout(600)
        chk(f"[{tag}] back on again", pg.evaluate("()=>document.documentElement.classList.contains('lf-glass')"))
        ctx.close()
    # remembered after reload, before the first paint
    ctx = br.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.evaluate("()=>localStorage.setItem('lf_glass','1')"); pg.reload()
    chk("glass is on from the first paint after a reload", pg.evaluate("()=>document.documentElement.classList.contains('lf-glass')"))
    ctx.close(); br.close()
errs=[e for e in errs if "Failed to load resource" not in e]
chk("no page errors", not errs, errs[:4])
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
