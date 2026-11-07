"""Leafline 11: leaderboard data + ranking + badges, announcements board (desktop engine AND website),
animated picture uploads, migration-not-run behaviour, themes, lead generation lock, intro and phone layout."""
import os, sys, tempfile, time, json, base64, io, uuid, threading, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "james", "tim")}
for p in F.t["profiles"]: p["must_change_password"] = False
import leafline_backend as B
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
def until(f, t=15):
    t0 = time.time()
    while time.time() - t0 < t:
        if f(): return True
        time.sleep(.2)
    return False
TZ = ZoneInfo("America/Toronto"); TODAY = datetime.now(TZ).date()
now = datetime.now(timezone.utc)
def calls(who, n, days_ago=0, outcome="no_answer"):
    t = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time(), TZ).replace(hour=12).astimezone(timezone.utc)
    for j in range(n):
        F.t["call_log"].append(dict(id=str(uuid.uuid4()), lead_id=None, employee_id=ids[who], phone="", started_at=(t + timedelta(minutes=j)).isoformat(), outcome=outcome, notes="", source="app", client_op_id=str(uuid.uuid4())))
calls("gio", 30); calls("gio", 5, 0, "meeting_booked"); calls("tim", 12); calls("tim", 7, 0, "meeting_booked"); calls("james", 120, 2)
F.t["deals"].append(dict(id=str(uuid.uuid4()), client="A", upfront=1000, monthly=100, months=0, closed_at=TODAY.isoformat(), first_bill=(TODAY + timedelta(days=40)).isoformat(), notes="", owner_id=ids["tim"], version=1, updated_at=F.now(), created_at=F.now()))
F.t["deals"].append(dict(id=str(uuid.uuid4()), client="B", upfront=0, monthly=250, months=3, closed_at=(TODAY - timedelta(days=70)).isoformat(), first_bill=(TODAY - timedelta(days=70)).isoformat(), notes="", owner_id=ids["gio"], version=1, updated_at=F.now(), created_at=F.now()))

print("1. desktop engine")
api = B.Api(); api._ready.set()
check("sign in", api.sign_in("gio", "Gio123")["ok"])
check("sync caught up and detected the 5th migration", until(lambda: api._sync.status["state"] == "synced" and api._sync.caps.get("media") is True))
b = api.get_board()
check("board data: active people, daily stats and deal schedules", b["ok"] and len(b["people"]) == 3 and len(b["stats"]) >= 3 and len(b["deals"]) == 2 and b["deals"][0].keys() >= {"owner_id", "monthly", "first_bill"})
check("board is cached for offline use", json.loads(api._sync._kv("board"))["ok"])
F.down = True; bo = api.get_board(); F.down = False
check("offline: last board shown and marked stale", bo["ok"] and bo["stale"])
r = api.get_posts(); check("empty board", r["ok"] and r["posts"] == [])
check("post needs a title", not api.save_post({"title": "  ", "body": "x"})["ok"])
r = api.save_post({"title": "  Big   news ", "body": "Hello team", "kind": "idea"}); pid = r["post"]["id"]
check("post created with my name and kind", r["ok"] and r["post"]["author_id"] == ids["gio"] and r["post"]["title"] == "Big news" and r["post"]["kind"] == "idea")
check("unknown kind falls back to announcement", api.save_post({"title": "x", "kind": "spam"})["post"]["kind"] == "announcement")
check("react", api.post_op("react", pid, "🔥")["ok"])
P = {p["id"]: p for p in api.get_posts()["posts"]}
check("reaction stored", P[pid]["reactions"].get("🔥") == [ids["gio"]])
api.post_op("react", pid, "🔥"); P = {p["id"]: p for p in api.get_posts()["posts"]}
check("second press removes the reaction", not P[pid]["reactions"].get("🔥"))
check("only the five reactions are allowed", not api.post_op("react", pid, "💩")["ok"])
check("comment", api.post_op("comment", pid, "  nice  ")["ok"]); P = {p["id"]: p for p in api.get_posts()["posts"]}
check("comment stored and trimmed", [c["body"] for c in P[pid]["comments"]] == ["nice"])
check("empty comment refused", not api.post_op("comment", pid, "   ")["ok"])
check("bad ids refused", not api.post_op("delete", "1 or 1=1")["ok"])
check("pin", api.post_op("pin", pid, True)["ok"] and [p for p in F.t["posts"] if p["id"] == pid][0]["pinned"] is True)
api2 = None
# another employee edits (business rule: everyone may edit); the author stays, the editor is recorded
import requests
tok = requests.post(F.url + "/auth/v1/token?grant_type=password", json={"email": "tim@leaflineweb.com", "password": "Tim123"}).json()["access_token"]
h = {"Authorization": "Bearer " + tok, "apikey": "x", "Content-Type": "application/json"}
requests.patch(F.url + "/rest/v1/posts?id=eq." + pid, headers=h, data=json.dumps({"title": "Edited by Tim", "author_id": ids["tim"]}))
row = [p for p in F.t["posts"] if p["id"] == pid][0]
check("a teammate can edit; author can't be rewritten; editor recorded", row["title"] == "Edited by Tim" and row["author_id"] == ids["gio"] and row["edited_by"] == ids["tim"])
x = requests.post(F.url + "/rest/v1/posts", headers=h, data=json.dumps({"title": "fake", "author_id": ids["gio"]}))
check("nobody can post in someone else's name", x.status_code == 403)
check("delete removes the post and its comments", api.post_op("delete", pid)["ok"] and not [c for c in F.t["post_comments"] if c["post_id"] == pid])
# media
png = io.BytesIO(); __import__("PIL.Image").Image.new("RGB", (40, 40), (10, 200, 90)).save(png, "PNG")
gif = io.BytesIO(); from PIL import Image
fr = [Image.new("RGB", (30, 30), (i * 40, 90, 60)) for i in range(4)]; fr[0].save(gif, "GIF", save_all=True, append_images=fr[1:], duration=100, loop=0)
du = lambda b, m: f"data:{m};base64," + base64.b64encode(b).decode()
thumb = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 50).decode()
G = [p for p in F.t["profiles"] if p["username"] == "gio"][0]
r = api.upload_media("avatar", du(gif.getvalue(), "image/gif"), thumb)
check("animated GIF uploaded as-is (frames kept)", r["ok"] and r["url"].endswith(".gif") and Image.open(io.BytesIO(F.files[r["url"].split("/public/")[1]][0])).n_frames == 4)
check("profile points at it, with a still copy for reduced motion", G["avatar_url"] == r["url"] and G["avatar"] == thumb and api.boot()["auth"]["me"]["media"]["avatar_url"] == r["url"])
old = r["url"].split("/public/")[1]; r2 = api.upload_media("avatar", du(png.getvalue(), "image/png"), thumb)
check("replacing it deletes the old file", r2["ok"] and old not in F.files and r2["url"].endswith(".png"))
check("a file pretending to be an image is refused", not api.upload_media("avatar", du(b"<svg onload=alert(1)>", "image/png"))["ok"])
check("over 8 MB refused", not api.upload_media("banner", du(b"GIF89a" + b"0" * (8 * 1024 * 1024), "image/gif"))["ok"])
check("unknown kind refused", not api.upload_media("evil", du(png.getvalue(), "image/png"))["ok"])
rb = api.upload_media("banner", du(png.getvalue(), "image/png"))
check("banner upload + position", rb["ok"] and api.set_banner_pos(150)["ok"] and G["banner_pos"] == 100 and api.set_banner_pos(25)["ok"] and G["banner_pos"] == 25)
check("people list carries the picture links for the team", any(p.get("avatar_url") == r2["url"] for p in api._sync.people()) or until(lambda: any(p.get("avatar_url") == r2["url"] for p in (api.get_team() and api._sync.people()))))
check("clear", api.clear_media("banner")["ok"] and G["banner_url"] is None)
print("2. before the 5th migration is run")
F.posts_cap = False; F.media_cap = False; api._sync.caps["media"] = None
r = api.get_posts(); check("board explains the missing update instead of failing", not r["ok"] and r.get("need_migration"))
r = api.upload_media("avatar", du(png.getvalue(), "image/png")); check("animated upload explains the missing update", not r["ok"] and "5th database update" in r["error"])
check("the rest keeps working", api.get_board()["ok"] and api.set_avatar(thumb)["ok"])
F.posts_cap = True; F.media_cap = True; api._sync.caps["media"] = None

print("3. website: ranking, badges, board, themes, lead generation")
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
from playwright.sync_api import sync_playwright
errs = []; reqs = []
def login(pg, u, pw):
    pg.fill("#lgUser", u); pg.fill("#lgPass", pw); pg.click("#lgGo"); pg.wait_for_selector("#login.on", state="detached", timeout=8000)
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=15000)
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(f"http://127.0.0.1:{port}/"); pg.wait_for_selector("#login.on")
    check("automated browsers skip the intro (tests stay fast)", pg.locator("#intro").count() == 0)
    login(pg, "gio", "Gio123")
    pg.evaluate("go('board')"); pg.wait_for_selector(".pod.p1", timeout=10000); time.sleep(.8)
    week = pg.evaluate("(()=>{const d=B.data,[f,t]=rangeOf('week',d.today);return tally(d,f,t)})()")
    start = TODAY - timedelta(days=TODAY.weekday())
    exp_j = 120 if TODAY - timedelta(days=2) >= start else 0
    check("calls counted from the real call log", week[ids["gio"]]["calls"] == 35 and week[ids["tim"]]["calls"] == 19 and week[ids["james"]]["calls"] == exp_j)
    check("meetings = calls logged as 'meeting booked'", week[ids["tim"]]["meetings"] == 7 and week[ids["gio"]]["meetings"] == 5)
    mon = pg.evaluate("(()=>{const d=B.data,[f,t]=rangeOf('month',d.today);return tally(d,f,t)})()")
    allt = pg.evaluate("(()=>{const d=B.data;return tally(d,'2000-01-01',d.today)})()")
    def sched(first, n, months):
        out = []; y, m, d0 = first.year, first.month, first.day
        for k in range(months):
            t = y * 12 + m - 1 + k; yy, mm = divmod(t, 12); import calendar
            ds = date(yy, mm + 1, min(d0, calendar.monthrange(yy, mm + 1)[1]))
            if ds > TODAY: break
            out.append(ds)
        return out
    g_all = 250 * len(sched(TODAY - timedelta(days=70), 0, 3))
    check("money = payments actually collected (upfront today, future monthly not counted)", allt[ids["tim"]]["money"] == 1000 and allt[ids["gio"]]["money"] == g_all)
    check("this month only counts this month's payments", mon[ids["tim"]]["money"] == 1000 and mon[ids["gio"]]["money"] == 250 * len([d for d in sched(TODAY - timedelta(days=70), 0, 3) if d.month == TODAY.month and d.year == TODAY.year]))
    first = pg.inner_text(".pod.p1 h4"); check("podium #1 is the top caller this week", first == ("James" if exp_j > 35 else "Gio"))
    pg.click("#lbM [data-m=meetings]"); time.sleep(.8); check("switching to meetings re-ranks", pg.inner_text(".pod.p1 h4") == "Tim")
    pg.click("#lbM [data-m=money]"); pg.click("#lbP [data-p=all]"); time.sleep(.8)
    check("money ranking, all time", pg.inner_text(".pod.p1 h4") == ("Tim" if 1000 >= g_all else "Gio") and "$" in pg.inner_text(".pod.p1 .v"))
    check("choice is remembered", pg.evaluate("getP('lbMetric')") == "money" and pg.evaluate("getP('lbPeriod')") == "all")
    bd = pg.evaluate("B.badges")
    check("badges from real data: Meeting Machine + Revenue Champion go to Tim, so he is MVP", "meetings" in bd[ids["tim"]] and "revenue" in bd[ids["tim"]] and bd[ids["tim"]][0] == "mvp")
    check("Deal Closer for a deal in the last 30 days only", "closer" in bd[ids["tim"]] and "closer" not in bd[ids["gio"]])
    check("Century Club for 100+ calls in one day", ("century" in bd[ids["james"]]) == True)
    check("Rising Star needs 20+ calls and growth (Gio: 35 vs 0)", "rising" in bd[ids["gio"]] and "rising" not in bd[ids["tim"]])
    pg.evaluate("go('team')"); pg.wait_for_selector(".tm-p .badge-i", timeout=10000)
    check("badges show on the Team page", pg.locator(".tm-p .badge-i").count() >= 3)
    print("   announcements")
    pg.evaluate("go('posts')"); pg.wait_for_selector("#psTitle"); time.sleep(.6)
    pg.click("#psTitle"); pg.fill("#psTitle", "Website test post"); pg.fill("#psBody", "Line 1\nLine 2"); pg.click('#psKind [data-k="update"]'); pg.click("#psPost")
    pg.wait_for_selector(".post h3:has-text('Website test post')", timeout=8000)
    wp = [x for x in F.t["posts"] if x["title"] == "Website test post"][0]
    check("posted from the website with author and kind", wp["author_id"] == ids["gio"] and wp["kind"] == "update" and wp["body"] == "Line 1\nLine 2")
    pg.click(".post [data-rx='👍']"); time.sleep(1.2); check("reaction from the website", any(r["post_id"] == wp["id"] and r["emoji"] == "👍" for r in F.t["post_reactions"]))
    pg.click(".post [data-cm]"); pg.fill(".post .cadd .inp", "From the web"); pg.press(".post .cadd .inp", "Enter"); time.sleep(1.5)
    check("comment from the website (Enter sends)", any(c["post_id"] == wp["id"] and c["body"] == "From the web" for c in F.t["post_comments"]))
    pg.hover(".post .au"); pg.wait_for_selector(".hcard.on", timeout=4000)
    check("hovering the author shows a profile preview with badges and stats", "Gio" in pg.inner_text(".hcard") and "Calls this wk" in pg.inner_text(".hcard"))
    pg.mouse.move(5, 5); time.sleep(.8); check("preview closes when the mouse leaves", pg.locator(".hcard").count() == 0)
    pg.click(".post [data-menu]"); pg.click(".post [data-act=edit]"); pg.fill("#epT", "Edited on the web"); pg.click(".dlg [data-ok]"); time.sleep(1.2)
    check("edit from the website records the editor", wp["title"] == "Edited on the web" and wp["edited_by"] == ids["gio"])
    pg.click(".post [data-menu]"); pg.click(".post [data-act=del]"); pg.click(".dlg [data-ok]"); time.sleep(1.5)
    check("delete from the website", not [x for x in F.t["posts"] if x["id"] == wp["id"]])
    F.posts_cap = False; pg.evaluate("loadPosts(true)"); time.sleep(1)
    check("website explains the missing database update", "5th database update" in pg.inner_text("#psList")); F.posts_cap = True
    print("   themes, lead generation, reduced motion")
    pg.evaluate("go('account')"); pg.wait_for_selector("#themeCard [data-th=midnight]"); pg.click("#themeCard [data-th=midnight]"); time.sleep(1)
    check("theme switches and is saved", pg.evaluate("document.documentElement.dataset.theme") == "midnight" and pg.evaluate("localStorage.getItem('lf_theme')") == "midnight" and pg.evaluate("getP('theme')") == "midnight")
    pg.reload(); pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=15000)
    check("theme survives a reload (no flash: applied before the page draws)", pg.evaluate("document.documentElement.dataset.theme") == "midnight")
    pg.evaluate("go('account')"); pg.wait_for_selector("#lgTgl")
    check("lead generation is OFF by default", pg.get_attribute("#lgTgl", "aria-checked") == "false" and "No requests" in pg.inner_text("#lgStt"))
    before = len(reqs); pg.click("#lgTgl"); time.sleep(.5)
    check("turning it on keeps the zero-spend lock", pg.get_attribute("#lgTgl", "aria-checked") == "true" and "locked" in pg.inner_text("#lgStt"))
    check("no request goes to Google or any places service", not [u for u in reqs[before:] if "google" in u or "overpass" in u or "places" in u])
    err = pg.evaluate("LEADGEN.search().then(()=>'ran').catch(e=>e.message)")
    check("search is blocked for a paid provider", "zero-spend" in err)
    pg.evaluate("go('find')"); time.sleep(.6); check("Find Leads shows the lead generation status on the website", pg.locator("#lgFind").count() == 1)
    ctx.close()
    print("4. intro, reduced motion and phone")
    c2 = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    c2.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})"); m = c2.new_page(); m.on("pageerror", lambda e: errs.append(str(e)))
    m.goto(f"http://127.0.0.1:{port}/")
    check("intro covers the app while it loads", m.is_visible("#intro"))
    m.wait_for_selector("#intro.ready", timeout=15000); check("logo becomes pressable when the app is ready", m.get_attribute("#introLogo", "aria-disabled") == "false" and "enter" in m.inner_text("#introTx").lower())
    m.tap("#introLogo"); m.wait_for_selector("#login.on"); time.sleep(.8)
    check("signed out: the intro hands over to the sign-in card", m.locator("#intro").count() == 0)
    login(m, "tim", "Tim123"); time.sleep(.5)
    check("reduced motion: no flying animation left on screen", m.locator(".flyer").count() == 0)
    check("phone: header picture and bottom tab bar", m.is_visible("#mAvBtn") and m.is_visible("#fmore") and not m.is_visible("#side"))
    m.tap("#fmore"); m.wait_for_selector("#msheet.show"); check("More opens a sheet with every page", m.locator("#sheetGrid button").count() == 11)
    m.tap("#sheetGrid [data-go=board]"); time.sleep(1.2)
    check("sheet closes and opens the page", not m.is_visible("#msheet .sp") or m.evaluate("!document.querySelector('#msheet').classList.contains('show')") and m.evaluate("S.page") == "board")
    check("More is lit up when the page lives in the sheet", m.evaluate("document.querySelector('#fmore').classList.contains('on')"))
    for pgname in ("board", "posts", "dash", "called", "calls", "profits", "account", "team"):
        m.evaluate(f"go('{pgname}')"); time.sleep(.9)
        check(f"phone: {pgname} has no sideways scroll", m.evaluate("(()=>{const p=document.querySelector('.page.on');return p.scrollWidth<=p.clientWidth+2})()"))
    c2.close(); br.close()
print("console errors:", errs[:5]); check("no console errors", not errs)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
