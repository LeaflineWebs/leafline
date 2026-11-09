"""11.12: the Find Leads filter (country, state/province, city, business type) on a phone and on a PC-sized window,
the app-wide scrollbars, and the filter staying put after a reload. Runs the real WEBSITE build (what phones load)."""
import os, sys, tempfile, threading, http.server, functools
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
ids = {n: F.add_user(n, n.title() + "123", "employee") for n in ("gio",)}
for p in F.t["profiles"]: p["must_change_password"] = False
LEADS = [  # id, name, btype, search label, address
    ("k1", "Kitchener Roofing", "Roofing", "Roofing | Kitchener, Ontario, Canada", "1 King St W, Kitchener, ON N2G 1A1"),
    ("l1", "London Roofing", "Roofing", "Roofing | London, Ontario, Canada", "200 Dundas St, London, ON N6A 1H3"),
    ("u1", "Baker Plumbing", "Plumbing", "Plumbing | London, England, United Kingdom", "10 Baker St, London NW1 6XE, UK"),
    ("m1", "Clinique Dentaire", "Dentist", "Dentist | Montréal, Quebec, Canada", "500 Rue Sainte-Catherine, Montréal, QC H3B"),
    ("t1", "Queen Reno", "Home Renovation", "Home Renovation | Toronto", "5 Queen St W, Toronto, ON M5H 2N2"),
    ("w1", "Cool Air HVAC", "HVAC", "HVAC | Waterloo, Ontario, Canada", "N/A"),
    ("b1", "Buffalo Roofing", "Roofing", "Roofing | Buffalo, New York, United States", "12 Main St, Buffalo, NY 14201"),
]
for i, (lid, name, bt, search, addr) in enumerate(LEADS):
    F.t["leads"].append(dict(id=lid, name=name, phone=f"(519) 555-02{i:02d}", owner_name="N/A", email="N/A", rating="4.5", reviews=str(100 - i), website="N/A",
                             address=addr, search=search, btype=bt, hours="", status="none", notes="", enriched=False, added_at="2026-11-07T14:00:00+00:00",
                             called_at=None, meeting_at=None, version=1, updated_at=F.now(), created_at=F.now(), phone_key=f"51955502{i:02d}"))
import build_web
site = tempfile.mkdtemp(); build_web.build(site)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
SHOWN = "()=>[...document.querySelectorAll('#list .li')].map(n=>n.dataset.id).sort()"
M = """(f)=>S.find.filter(l=>fltMatch(l,Object.assign(fltEmpty(),f))).map(l=>l.id).sort()"""

def open_page(br, w, h, phone):
    o = dict(viewport={"width": w, "height": h})
    if phone: o.update(is_mobile=True, has_touch=True, user_agent=UA)
    ctx = br.new_context(**o); pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/?nointro"); pg.wait_for_selector("#lgUser", state="visible", timeout=30000)
    pg.fill("#lgUser", "gio"); pg.fill("#lgPass", "Gio123"); pg.click("#lgGo")
    pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000)
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=40000)
    pg.evaluate("async()=>{document.querySelectorAll('.ov').forEach(x=>x.remove());await go('find');await new Promise(r=>setTimeout(r,500))}")
    return ctx, pg, errs
def typ(pg, k, v):
    pg.fill("#ff_" + k, v); pg.wait_for_timeout(450)

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    ctx, pg, errs = open_page(br, 390, 844, True)
    print("1. what matches")
    m = lambda f: pg.evaluate(M, f)
    check("City finds the start of a word ('kitch' finds Kitchener)", m({"city": "kitch"}) == ["k1"])
    check("City 'London' finds both Londons; adding Country Canada keeps only Ontario's", m({"city": "london"}) == ["l1", "u1"] and m({"city": "london", "country": "canada"}) == ["l1"])
    check("Province 'ON' and 'Ontario' find the same businesses (from the search area or the address)", m({"state": "on"}) == m({"state": "Ontario"}) == ["k1", "l1", "t1", "w1"])
    check("'ON' never matches inside a word (London, England stays out)", "u1" not in m({"state": "on"}))
    check("'NY' and 'New York' both find Buffalo", m({"state": "NY"}) == m({"state": "new york"}) == ["b1"])
    check("accents don't matter ('montreal' finds Montréal)", m({"city": "montreal"}) == ["m1"])
    check("Business type matches the start of a word ('roof' finds Roofing)", m({"type": "roof"}) == ["b1", "k1", "l1"])
    check("several values with commas: any of them ('roofing, dentist')", m({"type": "roofing, dentist"}) == ["b1", "k1", "l1", "m1"])
    check("boxes together must all match (Roofing in Ontario)", m({"type": "roofing", "state": "ontario"}) == ["k1", "l1"])
    check("Country 'United States' finds Buffalo; 'USA' too", m({"country": "united states"}) == ["b1"] and m({"country": "usa"}) == ["b1"])

    print("2. on a phone")
    check("the Filter button is in the tools row", pg.is_visible("#fltBtn") and not pg.is_visible("#fltBox"))
    pg.tap("#fltBtn"); pg.wait_for_timeout(300)
    check("tapping it opens Country, State, City and Business type", all(pg.is_visible("#ff_" + k) for k in ("country", "state", "city", "type")))
    fs = pg.evaluate("()=>['country','state','city','type'].map(k=>parseFloat(getComputedStyle(document.getElementById('ff_'+k)).fontSize))")
    check(f"the boxes use 16px text, so iPhones don't zoom in ({fs})", all(f >= 16 for f in fs))
    check("nothing scrolls sideways with the filter open", pg.evaluate("()=>document.documentElement.scrollWidth<=innerWidth&&document.getElementById('fltBox').getBoundingClientRect().right<=innerWidth"))
    niche = pg.evaluate("()=>[...document.querySelectorAll('#fltNiche [data-niche]')].map(b=>b.textContent)")
    check(f"business types are offered as buttons, most leads first ({niche[:3]})", niche and niche[0].startswith("Roofing") and niche[0].endswith("3"))
    typ(pg, "state", "ontario")
    niche = pg.evaluate("()=>[...document.querySelectorAll('#fltNiche [data-niche]')].map(b=>b.dataset.niche)")
    check(f"the type buttons follow the area you picked ({niche})", sorted(niche) == ["HVAC", "Home Renovation", "Roofing"])
    pg.tap("#fltNiche [data-niche='Roofing']"); pg.wait_for_timeout(400)
    check("tapping a type fills Business type and filters", pg.input_value("#ff_type") == "Roofing" and pg.evaluate(SHOWN) == ["k1", "l1"])
    check("the list says how many match", pg.inner_text("#fSub").startswith("2 of 7 match your filter"))
    check("the Filter button shows how many boxes are in use", pg.inner_text("#fltN") == "2")
    pg.tap("#fltNiche [data-niche='HVAC']"); pg.wait_for_timeout(400)
    check("tapping a second type adds it (Roofing, HVAC)", pg.input_value("#ff_type") == "Roofing, HVAC" and pg.evaluate(SHOWN) == ["k1", "l1", "w1"])
    pg.tap("#fltDone"); pg.wait_for_timeout(300)
    chips = pg.evaluate("()=>[...document.querySelectorAll('#fltChips [data-fk]')].map(b=>b.textContent)")
    check(f"Done folds it away and shows what's filtered as chips ({chips})", not pg.is_visible("#fltBox") and chips == ["ontario", "Roofing", "HVAC"])
    check("the first lead is still near the top of the screen", pg.evaluate("()=>document.querySelector('#list .li').getBoundingClientRect().top<520"))
    pg.tap("#fltChips [data-fv='HVAC']"); pg.wait_for_timeout(400)
    check("tapping × on a chip removes just that value", pg.evaluate(SHOWN) == ["k1", "l1"] and pg.evaluate("()=>S.flt.type") == "Roofing")
    pg.tap("#allChk"); pg.wait_for_timeout(200)
    check("Select all ticks only the businesses the filter shows", pg.evaluate("()=>[...S.sel].sort()") == ["k1", "l1"])
    pg.tap("#selBar [data-sx]"); pg.wait_for_timeout(200)
    print("3. it stays after closing the app")
    pg.reload(); pg.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=40000); pg.wait_for_timeout(800)
    pg.evaluate("async()=>{document.querySelectorAll('.ov').forEach(x=>x.remove());await go('find');await new Promise(r=>setTimeout(r,500))}")
    check("after reopening, the same filter is still on", pg.evaluate(SHOWN) == ["k1", "l1"] and pg.evaluate("()=>S.scope") == "all")
    pg.tap("#fltBtn"); pg.wait_for_timeout(300)
    check("...and its boxes are filled in", pg.input_value("#ff_state") == "ontario" and pg.input_value("#ff_type") == "Roofing")
    typ(pg, "city", "zzz")
    check("no match: a clear message with a Clear filter button", "Nothing matches your filter" in pg.inner_text("#list") and pg.is_visible("#list [data-fclear]"))
    pg.tap("#list [data-fclear]"); pg.wait_for_timeout(400)
    check("Clear filter shows everything again and empties the boxes", len(pg.evaluate(SHOWN)) == 7 and pg.input_value("#ff_city") == "" and pg.inner_text("#fltN") == "" and not pg.is_visible("#fltChips"))
    typ(pg, "type", "roof"); pg.fill("#gq", "kitchener") if pg.is_visible("#gq") else pg.evaluate("()=>{S.q='kitchener';renderFind()}"); pg.wait_for_timeout(300)
    check("works together with the search box", pg.evaluate(SHOWN) == ["k1"])
    pg.evaluate("()=>{S.q='';const g=document.getElementById('gq');if(g)g.value='';renderFind()}")
    pg.tap("#fltClearB"); pg.wait_for_timeout(400)
    check("the Clear button in the box resets everything", len(pg.evaluate(SHOWN)) == 7)
    ctx.close()

    print("4. small phone and PC-sized window")
    ctx, pg, errs2 = open_page(br, 360, 740, True)
    pg.tap("#fltBtn"); pg.wait_for_timeout(300)
    check("on a 360px phone it fits too", pg.evaluate("()=>document.documentElement.scrollWidth<=innerWidth&&[...document.querySelectorAll('#fltBox .inp')].every(i=>i.getBoundingClientRect().right<=innerWidth)"))
    ctx.close()
    ctx, pg, errs3 = open_page(br, 1440, 900, False)
    pg.click("#fltBtn"); pg.wait_for_timeout(300); pg.fill("#ff_city", "london"); pg.wait_for_timeout(450)
    r = pg.evaluate("()=>{const p=document.querySelector('#pg-find .pane').getBoundingClientRect();return [...document.querySelectorAll('#fltBox .inp,#fltBox .btn')].every(e=>{const b=e.getBoundingClientRect();return b.left>=p.left&&b.right<=p.right})}")
    check("on a PC the filter sits inside the list panel", r and pg.evaluate(SHOWN) == ["l1", "u1"])
    rules = pg.evaluate("()=>[...document.styleSheets].flatMap(s=>{try{return [...s.cssRules].map(r=>r.cssText)}catch(e){return []}}).filter(t=>t.includes('::-webkit-scrollbar'))")
    check("scrollbars are restyled everywhere: no arrow buttons, rounded theme-coloured thumb",
          any("::-webkit-scrollbar-button" in t and "display: none" in t for t in rules) and any("::-webkit-scrollbar-thumb" in t and "border-radius" in t and "--accent-rgb" in t for t in rules))
    check("no page errors", not (errs + errs2 + errs3) or print(errs + errs2 + errs3))
    br.close()
print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
