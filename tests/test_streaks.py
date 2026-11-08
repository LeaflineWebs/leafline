"""Call streaks (11.5): rules, colours, the Team page section and the badge on profiles."""
import os, sys, tempfile, threading, time, json
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
F.t["settings"].append(dict(key="daily_targets", value={"calls": 50, "connections": 20, "meetings": 3, "sales": 1}))
TZ = ZoneInfo("America/Toronto"); TODAY = datetime.now(TZ).date()
def calls(who, day, n):
    t = datetime.combine(day, datetime.min.time(), TZ).replace(hour=11).astimezone(timezone.utc)
    for j in range(n):
        F.t["call_log"].append(dict(id=str(uuid.uuid4()), lead_id=None, employee_id=ids[who], phone="", started_at=(t + timedelta(seconds=j)).isoformat(),
                                    outcome="no_answer", notes="", source="app", client_op_id=str(uuid.uuid4())))
d, k = TODAY - timedelta(days=1), 0                    # Tim: the last 12 workdays at the goal
while k < 12:
    if d.weekday() < 5: calls("tim", d, 55); k += 1
    d -= timedelta(days=1)
import leafline_backend as B
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)

api = B.Api(); api._ready.set(); assert api.sign_in("gio", "Gio123")["ok"]
t0 = time.time()
while api._sync.status["state"] != "synced" and time.time() - t0 < 20: time.sleep(.2)
b = api.get_board()
check("leaderboard data carries the team's daily call target", b["ok"] and b["targets"]["calls"] == 50)
srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); port = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, port, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()

# pure rules, fed with a hand-made calendar (2026-11-02 is a Monday)
RULES = r"""(cases)=>cases.map(([today,days])=>{B.data={today,people:[],stats:Object.entries(days).map(([day,c])=>({day,employee_id:'x',calls:c})),targets:{calls:100}};B.at=Math.random();
  const s=streakOf('x');return [s.n,s.best,s.doneToday]})"""
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    pg = br.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?t=tok"); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=20000)
    print("1. rules")
    keep = pg.evaluate("()=>JSON.stringify(B.data)")
    r = pg.evaluate(RULES, [
        ["2026-11-06", {"2026-11-02": 25, "2026-11-03": 30, "2026-11-04": 25, "2026-11-05": 26}],             # Mon-Thu hit, Friday still going
        ["2026-11-09", {"2026-11-05": 25, "2026-11-06": 25}],                                                 # Thu+Fri, weekend off, Monday morning
        ["2026-11-09", {"2026-11-05": 25, "2026-11-06": 25, "2026-11-07": 25}],                               # ...and a bonus Saturday
        ["2026-11-06", {"2026-11-02": 25, "2026-11-03": 24, "2026-11-04": 25, "2026-11-05": 25}],             # missed Tuesday by one call
        ["2026-11-06", {"2026-11-02": 25, "2026-11-03": 25, "2026-11-06": 25}],                               # skipped Wed+Thu, did Friday
        ["2026-11-06", {}],
    ])
    check("the streak goal is 25 calls a day", pg.evaluate("()=>streakGoal()") == 25)
    check("4 workdays in a row, today not done yet: still 4 (today never breaks it)", r[0] == [4, 4, False])
    check("weekends don't break a streak", r[1] == [2, 2, False])
    check("hitting the goal on a weekend is a bonus day", r[2] == [3, 3, False])
    check("missing a workday (even by one call) resets it; best is remembered", r[3] == [2, 2, False])
    check("coming back after missed days starts again at 1, done today", r[4] == [1, 2, True])
    check("nobody starts with a streak", r[5] == [0, 0, False])
    tiers = pg.evaluate("()=>[0,2,3,5,10,15,20,30,45,60,99].map(streakTier)")
    check("tiers: 3 yellow, 5 orange, 10 dark orange, 15 red, 20 dark red, 30 purple, 45 dark purple, 60 blue", tiers == [-1, -1, 0, 1, 2, 3, 4, 5, 6, 7, 7])
    check("colours run yellow > orange > dark orange > red > dark red > purple > dark purple > blue",
          pg.evaluate("()=>STREAK.map(t=>t[1]).join()") == "#FFD60A,#FF9F1C,#E8590C,#E5383B,#A4161A,#A855F7,#6B21A8,#3B82F6")
    pg.evaluate("(k)=>{B.data=JSON.parse(k);B.at=Math.random()}", keep)
    print("2. Team page and profiles")
    pg.evaluate("async()=>{await go('team');await ensureBoard(true)}"); pg.wait_for_selector(".tm-p [data-stk] .stk-bar", timeout=10000)
    cards = pg.evaluate("()=>[...document.querySelectorAll('.tm-p')].map(c=>{const st=c.querySelector('[data-stk]'),last=c.querySelector('.last');return {pid:c.dataset.pid,after:!!(last&&last.nextElementSibling===st),lit:st.querySelectorAll('.stk-m.on').length,next:(st.querySelector('.stk-m.next')||{}).innerText,cap:st.querySelector('.stk-cap').innerText}})")
    check("every Team card has its own streak bar, right under the latest activity", len(cards) == 3 and all(c["after"] for c in cards))
    tim = next(c for c in cards if c["pid"] == ids["tim"])
    check("Tim: 12 days lights up the 3, 5 and 10 milestones; 15 is next, the rest stay grey", tim["lit"] == 3 and tim["next"] == "15")
    check("the caption shows the streak and today's progress out of 25", "12-day streak" in tim["cap"] and "/25 calls today" in tim["cap"] and "best 12" in tim["cap"])
    check("there's no separate streaks section any more", pg.evaluate("()=>!document.querySelector('#tmStk')"))
    check("Tim's card on the Team page shows his streak", pg.evaluate(f"()=>document.querySelector('.tm-p[data-pid=\"{ids['tim']}\"] h3 .stk').innerText.trim()") == "12")
    pg.evaluate(f"()=>showHover(document.querySelector('.tm-p [data-stk]'),'{ids['tim']}')")
    check("hovering someone shows their streak, with a tooltip", pg.evaluate("()=>{const s=document.querySelector('.hcard h4 .stk');return s&&s.innerText.trim()==='12'&&s.title.includes('12-day call streak')}"))
    pg.evaluate("()=>hideHover(true)")
    pg.evaluate(f"()=>personModal(personFull('{ids['gio']}'))")
    check("profile pop-up shows 0 for someone without a streak", pg.evaluate("()=>document.querySelector('.ov h2 .stk.none').innerText.trim()") == "0")
    check("no page errors", not errs or print(errs))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
