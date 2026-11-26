"""12.0.1: the data diet. The free Supabase plan has a monthly download limit, and Leafline used it up (the project was
locked with "exceed_egress_quota"): every open copy re-downloaded everyone's pictures and banners every minute, the Team
page reloaded every 8 seconds, the PC app synced every 4 seconds day and night, and every id of every table was
re-downloaded every minute. This counts the real requests made by the PC app and the website against the fake shared
database, and checks what happens while Supabase is locked (it answers 402): changes wait on the device and upload after."""
import os, sys, tempfile, threading, time, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "omar", "james")}
BIG = "data:image/jpeg;base64," + "A" * 50000
for p in F.t["profiles"]: p.update(must_change_password=False, avatar=BIG, banner=BIG + "B" * 60000)
for i in range(300):
    F.t["leads"].append(dict(id=f"L{i}", name=f"Biz {i}", phone=f"(519) 555-{1000+i}", owner_name="N/A", email="N/A", rating="4", reviews="3", website="N/A", address="1 St", search="Roofing | London",
                             btype="Roofing", hours="", status="none", notes="", enriched=False, added_at=F.now(), called_at=None, meeting_at=None, called_by=None, version=1,
                             updated_at=F.now(), created_at=F.now(), phone_key=f"519555{1000+i}"))
import leafline_backend as B, leafline_sync as LS
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c, extra=None):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l, "" if extra is None else extra)
def log_since(t0, path=None): return [r for r in F.reqlog if r[0] >= t0 and (path is None or r[2].endswith(path))]
heavy = lambda rs: [r for r in rs if r[2].endswith("/profiles") and r[1] == "GET" and ("avatar" in r[3].split(",") or r[3] in ("*", "") or "banner" in r[3].split(","))]

api = B.Api(); api._ready.set()
srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()

print("1. the PC app")
r = api.sign_in("gio", "Gio123")
check("Gio signs in on the PC app", r.get("ok"), r)
t0 = time.time()
while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.2)
check("the pace constants: 10 s in use, 90 s idle, pictures every 30 min, deletion check every 15 min",
      LS.POLL == 10.0 and LS.IDLE_POLL == 90.0 and LS.HEAVY_S == 1800 and LS.RECON_S == 900)
api.ui_state(True); time.sleep(12); t0 = time.time(); time.sleep(36)          # what the page reports when hidden / untouched
n = len([r for r in log_since(t0, "/leads") if r[1] == "GET"])
check(f"idle (nobody using the app): at most 1 sync in 36 s ({n}; it was 9 before)", n <= 1, n)
t0 = time.time()
api.ui_state(False); time.sleep(36)
n = len([r for r in log_since(t0, "/leads") if r[1] == "GET"])
check(f"in use: about every 10 s ({n} syncs in 36 s; it was 9 before)", 2 <= n <= 5, n)
t0 = time.time()
for _ in range(5): api.get_team(); api.get_board(); api.get_people()
hv = heavy(log_since(t0))
check(f"5 team, leaderboard and people loads download pictures at most once ({len(hv)} heavy requests)", len(hv) <= 1, hv)
check("...but still show everyone's picture", all((p.get("avatar") or "") == BIG for p in api.get_team().get("people", [])) if api.get_team().get("ok") else False,
      [len(p.get("avatar") or "") for p in api.get_team().get("people", [])])
ids_reqs = [r for r in F.reqlog if r[1] == "GET" and r[3] == "id"]
check(f"the every-id deletion check ran once at start, not every minute ({len(ids_reqs)} requests for 4 tables)", len(ids_reqs) <= 4, len(ids_reqs))

print("2. while Supabase is locked (402), and after")
F.paused = True
api.save_lead("L1", "Sam Lee", "Call back Monday"); api._sync.wake.set(); time.sleep(4)
st = api.sync_status() if hasattr(api, "sync_status") else api._sync.status
check(f"the PC app says the shared database is paused, in plain words ({st.get('state')}: {str(st.get('error') or st.get('detail') or '')[:60]})",
      st.get("state") == "offline" and "paused" in str(st).lower(), st)
check("...and keeps the change on this computer", next(l for l in F.t["leads"] if l["id"] == "L1")["notes"] == "" and api._sync._counts()[0] >= 1)
api2 = B.Api(); r = api2.sign_in("tim", "Tim123")
check("signing in while it's locked says why", not r.get("ok") and "paused" in r.get("error", ""), r)
F.paused = False; api._sync.wake.set(); t0 = time.time()
while next(l for l in F.t["leads"] if l["id"] == "L1")["notes"] != "Call back Monday" and time.time() - t0 < 30: time.sleep(.5); api._sync.wake.set()
check("when it's back, the waiting change uploads by itself", next(l for l in F.t["leads"] if l["id"] == "L1")["notes"] == "Call back Monday")

api._sync.stop.set(); api._sync.wake.set(); time.sleep(1)   # stop the PC app's syncing so it isn't counted below
print("3. the website")
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
ws = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); threading.Thread(target=ws.serve_forever, daemon=True).start()
WEB = f"http://127.0.0.1:{ws.server_address[1]}/?nointro"
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(WEB); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", "omar"); pg.fill("#lgPass", "Omar123"); pg.press("#lgPass", "Enter")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000); pg.wait_for_timeout(4000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    t0 = time.time(); pg.mouse.move(300, 300); pg.wait_for_timeout(30000)
    n = len([r for r in log_since(t0, "/leads") if r[1] == "GET" and r[4] == "web"])
    check(f"website in use: about every 10 s ({n} syncs in 30 s; it was 6 before)", 2 <= n <= 4, n)
    t0 = time.time(); pg.evaluate("async()=>{await go('team')}"); pg.wait_for_timeout(50000)
    team_loads = len([r for r in log_since(t0, "/rpc/daily_stats")])
    hv = heavy(log_since(t0))
    check(f"Team page open for 50 s: refreshed about once, not 6 times ({team_loads} loads)", team_loads <= 3, team_loads)
    check(f"...and no pictures or banners downloaded again ({len(hv)})", len(hv) <= 1, hv)
    check("...while everyone's picture still shows", pg.evaluate("()=>(S.people||[]).filter(p=>p.avatar&&p.avatar.length>40000).length") >= 3)
    F.paused = True; pg.wait_for_timeout(13000)
    txt = pg.evaluate("()=>document.querySelector('#syncBtn')?document.querySelector('#syncBtn').getAttribute('title')||document.querySelector('#syncBtn').innerText:''")
    check(f"the website says the shared database is paused, in plain words ({txt[:70]})", "paused" in txt.lower() and pg.inner_text("#syncTx").startswith("Paused"), [txt, pg.inner_text("#syncTx")])
    pg2 = br.new_page(); pg2.goto(WEB); pg2.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg2.fill("#lgUser", "tim"); pg2.fill("#lgPass", "Tim123"); pg2.press("#lgPass", "Enter"); pg2.wait_for_timeout(2500)
    check("website sign-in while locked explains it", "paused" in pg2.inner_text("body").lower(), pg2.inner_text("body")[:200])
    F.paused = False
    check("no page errors", not errs, errs[:3])
    br.close()
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
