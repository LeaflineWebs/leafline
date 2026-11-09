"""11.11: finding new leads from a phone (the website build on an iPhone-sized screen).
Google Places (answers faked here) when an admin saved a key, inside the monthly limit; otherwise the search is handed to
the same person's Leafline app on their PC (a real desktop engine here, with only the Google Maps browser part faked),
which runs it and uploads the leads. Also: Settings for the key, the 12th update not run yet, thoughts expiring."""
import os, sys, tempfile, threading, json, http.server, functools, time
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
def lead(i, phone, status="none", search="Old | Somewhere"):
    return dict(id=i, name="Lead " + i, phone=phone, owner_name="N/A", email="N/A", rating="4.0", reviews="5", website="N/A", address="N/A", search=search,
                btype="Roofing", hours="", status=status, notes="", enriched=False, added_at="2026-11-07T14:00:00+00:00", called_at=None, meeting_at=None,
                version=1, updated_at=F.now(), created_at=F.now(), phone_key="".join(c for c in phone if c.isdigit())[-10:])
F.t["leads"] += [lead("0xa:0x1", "(519) 555-0300", "green", "Roofing | Kitchener"), lead("0xa:0x2", "(519) 555-0301")]
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
KEY = "AIzaSyTEST_key-0123456789abcdefghijklm"

# ---- fake Google Places: page 1 (3 usable, one already called, one without a phone, one closed for good) + page 2
def place(pid, name, phone, **x):
    d = dict(id=pid, displayName={"text": name, "languageCode": "en"}, formattedAddress="1 King St W, Kitchener, ON N2G 1A1, Canada", businessStatus="OPERATIONAL")
    if phone: d["nationalPhoneNumber"] = phone
    d.update(x); return d
WEEK = [d + ": 12:00 AM – 11:59 PM" for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]   # Google's thin spaces
PAGE1 = {"places": [place("ChIJ_g1", "Grand Roofing", "(519) 555-0401", websiteUri="https://grand.example", rating=4.67, userRatingCount=212, regularOpeningHours={"weekdayDescriptions": WEEK}),
                    place("ChIJ_g2", "Called Before Roofing", "(519) 555-0300", rating=4.1, userRatingCount=8),
                    place("ChIJ_g3", "No Phone Roofing", None),
                    place("ChIJ_g4", "Closed Roofing", "(519) 555-0404", businessStatus="CLOSED_PERMANENTLY"),
                    place("ChIJ_g5", "Lead 0xa:0x2", "+1 519-555-0301", rating=4.9, userRatingCount=77)], "nextPageToken": "tok-2"}
PAGE2 = {"places": [place("ChIJ_g6", "Second Page Roofing", "(519) 555-0406", rating=3.9, userRatingCount=3)]}
G = dict(calls=[], mode="ok")
def google(route):
    r = route.request; cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "POST, OPTIONS"}
    if r.method == "OPTIONS": return route.fulfill(status=204, headers=cors)
    body = json.loads(r.post_data or "{}"); G["calls"].append(dict(body=body, key=r.headers.get("x-goog-api-key"), mask=r.headers.get("x-goog-fieldmask")))
    if G["mode"] == "badkey":
        return route.fulfill(status=400, headers=cors, content_type="application/json",
                             body=json.dumps({"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}))
    route.fulfill(status=200, headers=cors, content_type="application/json", body=json.dumps(PAGE2 if body.get("pageToken") == "tok-2" else PAGE1))

# ---- the PC: a real desktop engine signed in as Gio; only the Google Maps browser is faked
PC = dict(slow=False)
def fake_scrape(q, limit, say, stop):
    PC["q"] = q
    say("Collecting listings... 2 found", .2)
    for i, (n, ph) in enumerate((("PC Plumbing", "(226) 555-0501"), ("PC Drains", "(226) 555-0502")), 1):
        say(f"Reading listing {i}/2: {n}", .2 + .3 * i)
        yield dict(id=f"0xpc:0x{i}", name=n, phone=ph, address="5 Queen St, Waterloo, ON", website="N/A", rating="4.2", reviews=str(10 * i), hours="")
        for _ in range(60 if PC["slow"] else 4):
            if stop.is_set(): return
            time.sleep(.5)
B.gmaps_scrape = fake_scrape

def phone(br, who):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=UA)
    ctx.route("https://places.googleapis.com/**", google)
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", who); pg.fill("#lgPass", who.title() + "123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=40000)
    pg.evaluate("()=>document.querySelectorAll('.ov').forEach(x=>x.remove())")
    return ctx, pg, errs
def search(pg, city, btype, state="Ontario", country="Canada"):
    pg.evaluate("async()=>{await go('find')}"); pg.wait_for_timeout(400)
    if not pg.is_visible("#fType"): pg.tap("#fOpen"); pg.wait_for_timeout(300)
    pg.fill("#fCountry", country); pg.fill("#fState", state); pg.fill("#fCity", city); pg.fill("#fType", btype); pg.tap("#goBtn")
def done(pg, t=60000):
    pg.wait_for_function("!S.running", timeout=t); pg.wait_for_timeout(600); return pg.inner_text("#sText")
TEXT = "()=>document.getElementById('sText').textContent"

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    ctx, pg, errs = phone(br, "gio")
    print("1. the form on a phone")
    pg.evaluate("async()=>{await go('find')}"); pg.wait_for_timeout(500)
    check("this is the website build on a phone", pg.evaluate("()=>!!window.LF_API&&innerWidth<500"))
    check("Find Leads shows a 'Find new leads' button", pg.is_visible("#fOpen") and "Find new leads" in pg.inner_text("#fOpen"))
    check("the form stays folded away until you tap it (the list stays near the top)", not pg.is_visible("#fType") and pg.evaluate("()=>document.querySelector('#list .li').getBoundingClientRect().top<420"))
    pg.tap("#fOpen"); pg.wait_for_timeout(400)
    r = pg.evaluate("""()=>['fCountry','fState','fCity','fType','goBtn'].map(i=>{const b=document.getElementById(i).getBoundingClientRect();return [i,b.left>=0&&b.right<=innerWidth&&b.width>0,Math.round(b.height)]})""")
    check(f"tapping it shows location, business type and Search, all on screen ({r})", all(v for _, v, _ in r))
    check("Search is a big full-width button", r[4][2] >= 44 and pg.evaluate("()=>document.getElementById('goBtn').getBoundingClientRect().width>300"))
    check("nothing on the page scrolls sideways", pg.evaluate("()=>document.documentElement.scrollWidth<=innerWidth"))
    r = pg.evaluate("async()=>await api('search','Canada','','','')")
    check("a search without a business type is refused with a clear message", not r["ok"] and "business type" in r["error"])

    print("2. Google Places (a key is saved)")
    F.lead.update(key=KEY, cap=900, used=0)
    search(pg, "Kitchener", "roofing")
    t = done(pg)
    check(f"the search finishes ({t[:90]})", t.startswith("Done: 3 businesses to call"))
    check("two Google requests (the second page too)", len(G["calls"]) == 2 and G["calls"][1]["body"].get("pageToken") == "tok-2")
    c0 = G["calls"][0]
    check("Google gets the key, the search words and asks for phone numbers", c0["key"] == KEY and c0["body"]["textQuery"] == "roofing in Kitchener, Ontario, Canada" and "nationalPhoneNumber" in c0["mask"])
    check("the database counted both requests against the monthly limit", F.lead["used"] == 2)
    L = {l["id"]: l for l in F.t["leads"]}
    lab = "Roofing | Kitchener, Ontario, Canada"
    check("new businesses are saved for the whole team, labelled like a PC search", L["ChIJ_g1"]["search"] == lab and L["ChIJ_g6"]["search"] == lab and L["ChIJ_g1"]["added_by"] == ids["gio"])
    check("details come across: website, rating, reviews", L["ChIJ_g1"]["website"] == "https://grand.example" and L["ChIJ_g1"]["rating"] == "4.7" and L["ChIJ_g1"]["reviews"] == "212")
    check("a business already called is left out", "ChIJ_g2" not in L and L["0xa:0x1"]["status"] == "green" and L["0xa:0x1"]["search"] == "Roofing | Kitchener")
    check("no phone number or closed for good: left out", "ChIJ_g3" not in L and "ChIJ_g4" not in L)
    check("a business already in the list (same phone) moves into this search, no duplicate", "ChIJ_g5" not in L and L["0xa:0x2"]["search"] == lab)
    names = pg.evaluate("()=>[...document.querySelectorAll('#list .li .lt b')].map(b=>b.textContent)")
    check(f"the list shows just this search's businesses ({names})", sorted(names) == ["Grand Roofing", "Lead 0xa:0x2", "Second Page Roofing"])
    check("opening hours come through (Grand Roofing shows open)", pg.evaluate("()=>{const l=S.find.find(x=>x.id==='ChIJ_g1');return l&&l.open==='open'}"))
    check("each one has a Call button that dials", pg.evaluate("()=>[...document.querySelectorAll('#list .li .lcall')].every(a=>/^tel:\\+1519555/.test(a.getAttribute('href')))"))

    print("3. Google limit used up: handed to the PC")
    api = B.Api(); api._ready.set(); assert api.sign_in("gio", "Gio123")["ok"]
    t0 = time.time()
    while api._sync.status["state"] != "synced" and time.time() - t0 < 30: time.sleep(.3)
    dsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler); dport = dsrv.server_address[1]
    dsrv.RequestHandlerClass = B.make_handler(api, dport, "tok"); dsrv.daemon_threads = True; threading.Thread(target=dsrv.serve_forever, daemon=True).start()
    dpg = br.new_page(viewport={"width": 1440, "height": 900}); dpg.on("pageerror", lambda e: errs.append("PC: " + str(e)))
    dpg.goto(f"http://127.0.0.1:{dport}/?t=tok&nointro"); dpg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=60000)
    dpg.evaluate("async()=>{document.querySelectorAll('.ov').forEach(x=>x.remove());await go('find')}")
    F.lead.update(used=900)
    n_google = len(G["calls"])
    search(pg, "Waterloo", "plumbing")
    pg.wait_for_function(f"({TEXT})().includes('Sent to Leafline on your PC')", timeout=15000)
    check("the phone says the limit is used up and that it went to the PC", "limit is used up" in pg.evaluate(TEXT))
    pg.wait_for_function(f"({TEXT})().startsWith('Your PC:')", timeout=30000)
    check("then shows the PC's progress", "Your PC:" in pg.evaluate(TEXT))
    t = done(pg, 90000)
    check(f"the PC's search finishes on the phone ({t[:80]})", t.startswith("Done: 2 businesses to call") and "searched by your PC" in t)
    check("Google wasn't asked again", len(G["calls"]) == n_google)
    check("the PC ran it with the phone's words", PC.get("q") == "plumbing in Waterloo, Ontario, Canada")
    check("the PC's leads were uploaded for everyone", {"0xpc:0x1", "0xpc:0x2"} <= {l["id"] for l in F.t["leads"]})
    names = pg.evaluate("()=>[...document.querySelectorAll('#list .li .lt b')].map(b=>b.textContent)")
    check(f"...and show up on the phone ({names})", sorted(names) == ["PC Drains", "PC Plumbing"])
    req = F.t["lead_requests"][-1]
    check("the request is closed as done with the count", req["status"] == "done" and req["found"] == 2 and req["q"] == "Plumbing | Waterloo, Ontario, Canada")
    check("the PC is free again", not api._busy and api._remote is None)
    dpg.wait_for_timeout(1500)
    check(f"the PC's own screen showed the search from the phone and its results ({dpg.inner_text('#sText')[:60]})",
          dpg.evaluate("()=>S.current") == "Plumbing | Waterloo, Ontario, Canada" and dpg.inner_text("#sText").startswith("Done: 2")
          and sorted(dpg.evaluate("()=>[...document.querySelectorAll('#list .li .lt b')].map(b=>b.textContent)")) == ["PC Drains", "PC Plumbing"])

    print("4. stopping a PC search from the phone")
    PC["slow"] = True; F.lead.update(key="")
    search(pg, "Guelph", "hvac")
    pg.wait_for_function(f"({TEXT})().startsWith('Your PC:')", timeout=30000)
    check("without a key it goes straight to the PC", len(G["calls"]) == n_google)
    pg.tap("#goBtn")
    t = done(pg, 30000)
    check(f"Stop on the phone ends it ({t[:60]})", t.startswith("Stopped"))
    t0 = time.time()
    while api._busy and time.time() - t0 < 20: time.sleep(.3)
    check("...and the PC stops too", not api._busy and F.t["lead_requests"][-1]["status"] == "cancelled")
    PC["slow"] = False
    t0 = time.time()
    while api._remote is not None and time.time() - t0 < 20: time.sleep(.3)

    print("5. Google refuses the key: handed to the PC with the reason")
    F.lead.update(key=KEY, used=0); G["mode"] = "badkey"
    search(pg, "Cambridge", "painters")
    pg.wait_for_function(f"({TEXT})().includes('Sent to Leafline on your PC')||({TEXT})().startsWith('Your PC')", timeout=20000)
    t = pg.evaluate(TEXT)
    check(f"the phone says why ({t[:80]})", "isn't valid" in t or t.startswith("Your PC"))
    t = done(pg, 90000)
    check("the PC still finds the leads", t.startswith("Done:") and "searched by your PC" in t)
    G["mode"] = "ok"
    api._sync.stop.set()

    print("6. nobody's PC is on")
    ctx2, pg2, errs2 = phone(br, "tim")
    F.lead.update(key="")
    search(pg2, "Toronto", "bakery")
    pg2.wait_for_function(f"({TEXT})().includes('Waiting for it to start')", timeout=15000)
    check("Tim's phone waits for Tim's PC (Gio's PC never takes it)", F.t["lead_requests"][-1]["status"] == "pending" and F.t["lead_requests"][-1]["owner_id"] == ids["tim"])
    pg2.tap("#goBtn"); t = done(pg2, 20000)
    check("he can stop waiting", t.startswith("Stopped") and F.t["lead_requests"][-1]["status"] == "cancelled")

    print("7. Settings")
    pg2.evaluate("async()=>{await go('account')}"); pg2.wait_for_selector("#lgStt", timeout=15000)
    check("a teammate sees the status but no key box", "sent to your PC" in pg2.inner_text("#lgenCard") and not pg2.query_selector("#lgKey"))
    ctx2.close()
    ctx3, pg3, errs3 = phone(br, "james")
    pg3.evaluate("async()=>{await go('account')}"); pg3.wait_for_selector("#lgKey", timeout=15000)
    check("an admin sees the key box and the monthly limit", pg3.is_visible("#lgKey") and pg3.input_value("#lgCap") == "900")
    pg3.fill("#lgKey", "not a key"); pg3.tap("#lgSave"); pg3.wait_for_timeout(300)
    check("a pasted mistake is caught before saving", "doesn't look like" in pg3.inner_text("#lgNote") and F.lead["key"] == "")
    pg3.fill("#lgKey", KEY); pg3.fill("#lgCap", "500"); pg3.tap("#lgSave")
    pg3.wait_for_function("document.querySelector('#lgStt')&&document.querySelector('#lgStt').textContent.includes('Google Places is on')", timeout=15000)
    check("saving stores the key and limit", F.lead["key"] == KEY and F.lead["cap"] == 500)
    check("the key isn't shown again, only its last 4 characters", pg3.input_value("#lgKey") == "" and KEY[-4:] in pg3.get_attribute("#lgKey", "placeholder"))
    pg3.tap("#lgHelp"); pg3.wait_for_selector(".ov.on .kh")
    h = pg3.inner_text(".ov.on .kh")
    check("'How to get a free key' explains the steps, including the website restriction and a daily cap", "Places API (New)" in h and f"127.0.0.1:{port}/*" in h and "requests per day" in h)
    pg3.tap(".ov.on [data-x]"); pg3.wait_for_timeout(400)
    pg3.tap("#lgDel"); pg3.wait_for_function("document.querySelector('#lgStt')&&document.querySelector('#lgStt').textContent.includes('No Google key')", timeout=15000)
    check("an admin can remove the key", F.lead["key"] == "")

    print("8. before the 12th database update")
    F.lead_cap = False
    pg3.evaluate("async()=>{await go('dash');await go('account')}"); pg3.wait_for_function("document.querySelector('#lgStt')&&/12th/.test(document.querySelector('#lgStt').textContent)", timeout=15000)
    check("Settings says the 12th update is needed", True)
    search(pg3, "Ottawa", "dentist")
    pg3.wait_for_selector(".ov.on", timeout=20000)
    check("searching says the 12th update is needed", "12th database update" in pg3.inner_text(".ov.on"))
    F.lead_cap = True

    print("9. thought of the day lasts 24 hours")
    r = pg.evaluate("()=>[freshThought({thought:'x',thought_at:new Date(Date.now()-23*3600e3).toISOString()}),freshThought({thought:'x',thought_at:new Date(Date.now()-25*3600e3).toISOString()})]")
    check("shown at 23 hours, gone at 25", r == [True, False])
    r = pg.evaluate("""async()=>{localStorage.setItem('lf_ext',JSON.stringify({thought:'Dial more',thought_at:new Date(Date.now()-30*3600e3).toISOString()}));
      const a=await api('set_profile_ext',{thought:'Dial more'});return a.ok&&Date.now()-new Date(JSON.parse(localStorage.getItem('lf_ext')).thought_at).getTime()<60e3}""")
    check("posting the same thought again the next day shows it again", r)
    check("no page errors", not (errs + errs2 + errs3) or print(errs + errs2 + errs3))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
