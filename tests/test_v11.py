"""Leafline 11: leaderboard data + ranking + badges, announcements board (desktop engine AND website),
animated picture uploads, migration-not-run behaviour, themes, lead generation lock, intro and phone layout."""
import os, sys, tempfile, time, json, base64, io, uuid, threading, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")       # a Windows browser needs the real profile folder to start
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "james", "tim")}
for p in F.t["profiles"]: p["must_change_password"] = False
ids["newbie"] = F.add_user("newbie", "Temp1234", "employee")     # brand-new teammate: must pick a password first
[p for p in F.t["profiles"] if p["username"] == "newbie"][0]["must_change_password"] = True
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
check("board data: active people, daily stats and deal schedules", b["ok"] and len(b["people"]) == 4 and len(b["stats"]) >= 3 and len(b["deals"]) == 2 and b["deals"][0].keys() >= {"owner_id", "monthly", "first_bill"})
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
check("profile picture over 8 MB refused", "8 MB" in (api.upload_media("avatar", du(b"GIF89a" + b"0" * (8 * 1024 * 1024), "image/gif")).get("error") or ""))
check("banner over 100 MB refused (banners may be up to 100 MB)", "100 MB" in (api.upload_media("banner", du(b"GIF89a" + b"0" * (100 * 1024 * 1024), "image/gif")).get("error") or ""))
check("unknown kind refused", not api.upload_media("evil", du(png.getvalue(), "image/png"))["ok"])
rb = api.upload_media("banner", du(png.getvalue(), "image/png"))
check("banner upload + position", rb["ok"] and api.set_banner_pos(150)["ok"] and G["banner_pos"] == 100 and api.set_banner_pos(25)["ok"] and G["banner_pos"] == 25)
check("people list carries the picture links for the team", any(p.get("avatar_url") == r2["url"] for p in api._sync.people()) or until(lambda: any(p.get("avatar_url") == r2["url"] for p in (api.get_team() and api._sync.people()))))
check("clear", api.clear_media("banner")["ok"] and G["banner_url"] is None)
G0 = [p for p in F.t["profiles"] if p["username"] == "gio"][0]
check("'online' heartbeat runs on its own (teammates see you online consistently)", until(lambda: G0.get("last_seen") and (datetime.now(timezone.utc) - datetime.fromisoformat(G0["last_seen"].replace("Z", "+00:00"))).total_seconds() < 40))
print("1b. moving credit (6th migration)")
F.t["leads"].append(dict(id="L1", name="Oak Plumbing", phone="+1-519-555-0199", owner_name="N/A", email="N/A", rating="4.5", reviews="9", website="N/A", address="x", search="s", btype="Plumbing", hours="", status="green", notes="", enriched=False,
    added_at=F.now(), called_at=now.isoformat(), meeting_at=None, version=1, updated_at=F.now(), created_at=F.now(), phone_key="5195550199", called_by=ids["gio"]))
F.t["call_log"].append(dict(id=str(uuid.uuid4()), lead_id="L1", employee_id=ids["gio"], phone="", started_at=now.isoformat(), outcome="meeting_booked", notes="", source="app", client_op_id=str(uuid.uuid4())))
until(lambda: any(l["id"] == "L1" for l in api.get_called()))
def stat(who):
    r = [x for x in requests.post(F.url + "/rest/v1/rpc/daily_stats", headers={"Authorization": "Bearer " + api._sync.auth.token(), "apikey": "x"}, json={"p_from": TODAY.isoformat(), "p_to": TODAY.isoformat()}).json() if x["employee_id"] == ids[who]]
    return (sum(x["calls"] for x in r), sum(x["meetings"] for x in r))
g0, t0 = stat("gio"), stat("tim")
check("bad teammate refused", not api.set_credit("lead", "L1", "nope")["ok"])
r = api.set_credit("lead", "L1", ids["tim"]); L1 = [l for l in F.t["leads"] if l["id"] == "L1"][0]
check("Gio gives a meeting he booked to Tim", r["ok"] and L1["called_by"] == ids["tim"])
g1, t1 = stat("gio"), stat("tim")
check("the meeting now counts for Tim; the call itself stays with Gio", t1[1] == t0[1] + 1 and g1[1] == g0[1] - 1 and g1[0] == g0[0] and t1[0] == t0[0])
check("the team sees it in Activity", any(a["kind"] == "credit" and "gave Oak Plumbing to Tim" in a["summary"] for a in F.t["activity"]))
check("Called Leads shows the new name at once", [l for l in api.get_called() if l["id"] == "L1"][0]["called_by"] == ids["tim"])
r = api.set_credit("lead", "L1", ids["james"]); check("someone who isn't involved can't move it between two others", not r["ok"] and "Only the person" in r["error"])
r = api.set_credit("lead", "L1", ids["gio"]); check("but anyone can claim one that was booked for them", r["ok"] and L1["called_by"] == ids["gio"] and any("took credit for Oak Plumbing" in a["summary"] for a in F.t["activity"]))
F.credit_cap = False; r = api.set_credit("lead", "L1", ids["tim"]); F.credit_cap = True
check("before the 6th update: clear message, nothing changes", not r["ok"] and r.get("need_migration") and L1["called_by"] == ids["gio"])
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
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    ctx = br.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(f"http://127.0.0.1:{port}/"); pg.wait_for_selector("#login.on")
    check("automated browsers skip the intro (tests stay fast)", pg.locator("#intro").count() == 0)
    login(pg, "gio", "Gio123")
    pg.evaluate("go('board')"); pg.wait_for_selector(".pod.p1", timeout=10000); time.sleep(.8)
    week = pg.evaluate("(()=>{const d=B.data,[f,t]=rangeOf('week',d.today);return tally(d,f,t)})()")
    start = TODAY - timedelta(days=TODAY.weekday())
    exp_j = 120 if TODAY - timedelta(days=2) >= start else 0
    check("calls counted from the real call log", week[ids["gio"]]["calls"] == 36 and week[ids["tim"]]["calls"] == 19 and week[ids["james"]]["calls"] == exp_j)
    check("meetings = calls logged as 'meeting booked'", week[ids["tim"]]["meetings"] == 7 and week[ids["gio"]]["meetings"] == 6)
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
    pg.evaluate("B.data=null;B.at=0;S.team=null;go('posts')"); pg.wait_for_selector("#psTitle"); time.sleep(.6)
    requests.post(F.url + "/rest/v1/posts", headers={"Authorization": "Bearer " + api._sync.auth.token(), "apikey": "x", "Content-Type": "application/json"}, data=json.dumps({"title": "Pic check", "author_id": ids["gio"]}))
    pg.evaluate("loadPosts(true)"); pg.wait_for_function("document.querySelectorAll('.post .au .tav img').length>0", timeout=10000)
    check("profile pictures show in Announcements even when the page opens first", pg.locator(".post .au .tav img").count() >= 1)
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
    print("   @mentions + hover banner")
    pg.click("#psTitle"); pg.fill("#psTitle", ""); pg.type("#psTitle", "Thanks @Ti"); pg.wait_for_selector(".mpick button", timeout=3000)
    check("typing @ shows teammates to tag", "Tim" in pg.inner_text(".mpick"))
    pg.keyboard.press("Enter"); check("Enter puts the name in", pg.input_value("#psTitle") == "Thanks @Tim ")
    pg.type("#psTitle", "for the tip"); pg.click("#psPost"); pg.wait_for_selector(".post .ment", timeout=8000)
    check("the tag shows as a highlighted chip", pg.inner_text(".post .ment") == "@Tim")
    pg.hover(".post .ment"); pg.wait_for_selector(".hcard.on", timeout=4000); check("hovering a tag shows that person's preview", "Tim" in pg.inner_text(".hcard")); pg.mouse.move(5, 5); time.sleep(.6)
    requests.post(F.url + "/rest/v1/posts", headers=h, data=json.dumps({"title": "Nice work @gio", "body": "", "author_id": ids["tim"]}))
    pg.evaluate("loadPosts(true)"); pg.wait_for_function("document.querySelector('#toast').classList.contains('on')", timeout=8000)
    check("being tagged pops a notification with who did it", "Tim mentioned you" in pg.inner_text("#toast") and any("mentioned you" in n for n in pg.evaluate("S.notes.map(n=>n.text)")))
    check("your own name is highlighted differently", pg.locator(".post .ment.me").count() >= 1)
    pg.evaluate("loadPosts(true)"); time.sleep(1); check("the same tag isn't announced twice", pg.evaluate("S.notes.filter(n=>n.text.includes('mentioned you')).length") == 1)
    T = [x for x in F.t["profiles"] if x["username"] == "tim"][0]; T["banner"] = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode()
    pg.evaluate("Object.keys(PBAN).forEach(k=>delete PBAN[k])")
    pg.hover(f".post .au[data-au='{ids['tim']}']"); pg.wait_for_selector(".hcard.on .hb img", timeout=6000)
    check("hover preview now shows the banner (fetched on demand, not only on click)", pg.locator(".hcard .hb img").count() == 1); pg.mouse.move(5, 5); time.sleep(.6)
    W = f".post[data-id='{wp['id']}']"
    pg.click(W + " [data-menu]"); pg.click(W + " [data-act=edit]"); pg.fill("#epT", "Edited on the web"); pg.click(".dlg [data-ok]"); time.sleep(1.2)
    check("edit from the website records the editor", wp["title"] == "Edited on the web" and wp["edited_by"] == ids["gio"])
    pg.click(W + " [data-menu]"); pg.click(W + " [data-act=del]"); pg.click(".dlg [data-ok]"); time.sleep(1.5)
    check("delete from the website", not [x for x in F.t["posts"] if x["id"] == wp["id"]])
    F.posts_cap = False; pg.evaluate("loadPosts(true)"); time.sleep(1)
    check("website explains the missing database update", "5th database update" in pg.inner_text("#psList")); F.posts_cap = True
    print("   credit for deals, sharper pictures, charts")
    pg.evaluate("go('profits')"); time.sleep(1.5)
    dl = [d for d in pg.evaluate("S.deals") if d["client"] == "B"]
    if dl:
        pg.evaluate(f"dealModal(S.deals.find(d=>d.client==='B'))"); pg.wait_for_function("document.querySelector('#crWho') && document.querySelector('#crWho').value!==''", timeout=8000)
        check("deal shows who it's credited to", pg.input_value("#crWho") == ids["gio"])
        pg.select_option("#crWho", ids["tim"]); time.sleep(1.2)
        check("deal moved to Tim from the website", [d for d in F.t["deals"] if d["client"] == "B"][0]["owner_id"] == ids["tim"]); pg.keyboard.press("Escape")
    else: check("deal B visible on the website", False)
    q = pg.evaluate("""(async()=>{const c=document.createElement('canvas');c.width=1600;c.height=1200;const x=c.getContext('2d');for(let i=0;i<400;i++){x.fillStyle=`hsl(${i*7},60%,50%)`;x.fillRect((i*37)%1600,(i*53)%1200,60,60)}
      const b=await new Promise(r=>c.toBlob(r,'image/png'));const d=await pictureFromFile(new File([b],'a.png',{type:'image/png'}));const im=new Image();im.src=d;await im.decode();return [d.slice(0,15),d.length,im.naturalWidth]})()""")
    check("still copy of a picture is now sharp (up to 512 px) and fits the database", q[2] >= 384 and q[1] < 60000)
    check("all charts share one style", pg.locator("#pg-profits .bch").count() == 1 and pg.locator("#pg-profits svg rect.bar").count() == 0)
    pg.evaluate("go('dash')"); time.sleep(1.2); check("dashboard activity uses the shared chart", pg.locator("#pg-dash .bch .dcol").count() == 7)
    pg.evaluate("go('team')"); pg.wait_for_selector("#pg-team .bch", timeout=10000); check("team chart uses the shared chart", pg.locator("#pg-team .bch .dcol").count() == 14)
    print("   themes, lead generation, reduced motion")
    pg.evaluate("go('account')"); pg.wait_for_selector("#themeCard [data-th=midnight]"); pg.click("#themeCard [data-th=midnight]"); time.sleep(1)
    check("theme switches and is saved", pg.evaluate("document.documentElement.dataset.theme") == "midnight" and pg.evaluate("localStorage.getItem('lf_theme')") == "midnight" and pg.evaluate("getP('theme')") == "midnight")
    pg.reload(); pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=15000)
    check("theme survives a reload (no flash: applied before the page draws)", pg.evaluate("document.documentElement.dataset.theme") == "midnight")
    check("11 themes: the original 3 plus the rainbow and Obsidian", pg.evaluate("THEMES.map(t=>t[0]).join()") == "forest,emerald,midnight,ruby,amber,gold,lime,ocean,indigo,violet,obsidian")
    full = pg.evaluate("""()=>THEMES.slice(3).map(t=>{document.documentElement.dataset.theme=t[0];const c=getComputedStyle(document.documentElement);
        return [t[0],['--bg','--card','--accent','--accent-rgb','--nav-pill','--btn1','--bar','--logo2','--line'].every(k=>c.getPropertyValue(k).trim())&&c.getPropertyValue('--accent').trim()!=='#4ADE8B'||t[0]==='obsidian']})""")
    check("every new theme sets its own colours", all(ok_ for _, ok_ in full))
    pg.evaluate("document.documentElement.dataset.theme='midnight'")
    pg.click(".side .foot .thb"); pg.wait_for_selector(".thpop [data-th=ocean]"); pg.click(".thpop [data-th=ocean]"); time.sleep(.8)
    check("the sidebar theme button opens the list and switches theme", pg.evaluate("document.documentElement.dataset.theme") == "ocean" and pg.evaluate("getP('theme')") == "ocean")
    check("...and the button shows the new theme's name", pg.inner_text(".side .foot .thb").strip() == "Ocean")
    pg.reload(); pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=15000)
    check("a new theme also survives a reload", pg.evaluate("document.documentElement.dataset.theme") == "ocean")
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
    m.tap("#fmore"); m.wait_for_selector("#msheet.show"); check("More opens a sheet with every page", m.locator("#sheetGrid button").count() == 12)
    m.tap("#sheetGrid [data-go=board]"); time.sleep(1.2)
    check("sheet closes and opens the page", not m.is_visible("#msheet .sp") or m.evaluate("!document.querySelector('#msheet').classList.contains('show')") and m.evaluate("S.page") == "board")
    check("More is lit up when the page lives in the sheet", m.evaluate("document.querySelector('#fmore').classList.contains('on')"))
    for pgname in ("board", "posts", "dash", "called", "calls", "profits", "account", "team"):
        m.evaluate(f"go('{pgname}')"); time.sleep(.9)
        check(f"phone: {pgname} has no sideways scroll", m.evaluate("(()=>{const p=document.querySelector('.page.on');return p.scrollWidth<=p.clientWidth+2})()"))
    c2.close()
    print("   brand-new teammate on a phone (with the opening animation on)")
    c3 = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    c3.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})"); n = c3.new_page(); n.on("pageerror", lambda e: errs.append(str(e)))
    n.goto(f"http://127.0.0.1:{port}/"); n.wait_for_selector("#intro.ready", timeout=15000); n.tap("#introLogo"); n.wait_for_selector("#login.on"); time.sleep(1)
    n.fill("#lgUser", "newbie"); n.fill("#lgPass", "Temp1234"); n.tap("#lgGo"); n.wait_for_selector("#pwForm", state="visible", timeout=8000); time.sleep(.8)
    on_top = "(()=>{const e=document.querySelector('#pwNew'),r=e.getBoundingClientRect(),t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return t===e})()"
    check("new teammate sees the 'choose a password' card (nothing covering it)", n.evaluate(on_top))
    n.fill("#pwNew", "NewPass123!"); n.fill("#pwNew2", "NewPass123!"); n.tap("#pwGo"); n.wait_for_selector("#login.on", state="detached", timeout=10000); time.sleep(3.5)
    vis = "(()=>{const e=document.querySelector('#title'),r=e.getBoundingClientRect(),t=document.elementFromPoint(r.left+5,r.top+r.height/2);return !!t&&(t===e||e.contains(t))})()"
    check("after choosing a password the app is visible, not a green screen", n.evaluate(vis) and n.locator(".lens").count() == 0)
    c3.close(); br.close()
print("console errors:", errs[:5]); check("no console errors", not errs)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
