"""Messages, end to end: Gio in the desktop app, Tim and Omar on the website (plus Tim on a phone), all at once.
The database side is the REAL migration on a real Postgres (tests/pg/server.mjs), including row level security,
the private file bucket and the live (Realtime) connection.
Needs: Node + `npm install` in tests/pg, and Chrome/Edge (set LEAFLINE_CHROME on Windows)."""
import os, sys, tempfile, threading, time, json, http.server, functools, uuid
os.environ["NO_PROXY"] = "127.0.0.1,localhost"; os.environ["no_proxy"] = "127.0.0.1,localhost"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, "..", "backend"), os.path.join(HERE, "..", "tools"), HERE]
_BROWSER_HOME = os.environ.get("USERPROFILE", "")
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
import msg_harness
if not msg_harness.available():
    print("SKIPPED: run `npm install` in tests/pg first (needs Node)."); sys.exit(0)
from fake_supabase import Fake
F = Fake(); os.environ["SUPABASE_URL"] = F.url
F.msg_url = msg_harness.start_pg_server()
RT = F.msg_url.replace("http", "ws") + "/realtime/v1/websocket"; os.environ["LEAFLINE_REALTIME_URL"] = RT
ids = {n: F.add_user(n, n.title() + "123", "admin" if n == "james" else "employee") for n in ("gio", "tim", "omar", "james")}
for p in F.t["profiles"]: p["must_change_password"] = False
import requests
import leafline_backend as B
import build_web
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
def until(f, t=10):
    t0 = time.time()
    while time.time() - t0 < t:
        try:
            if f(): return True
        except Exception: pass
        time.sleep(.25)
    return False
def node(path, body, uid=None):
    return requests.post(F.msg_url + path, data=json.dumps(body), headers={"Content-Type": "application/json", **({"X-Uid": uid} if uid else {})}).json()

# website (Tim, Omar)
site = tempfile.mkdtemp(); build_web.build(site)
cfg = open(os.path.join(site, "config.js"), encoding="utf-8").read()
conf = json.loads(cfg[cfg.index("{"):cfg.rindex("}") + 1]); conf["realtime"] = RT
open(os.path.join(site, "config.js"), "w", encoding="utf-8").write("window.LF_CONFIG=%s;\n" % json.dumps(conf))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(s, *a): pass
web = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site)); WEB = f"http://127.0.0.1:{web.server_address[1]}/"
threading.Thread(target=web.serve_forever, daemon=True).start()
# desktop app (Gio)
api = B.Api(); api._ready.set(); assert api.sign_in("gio", "Gio123")["ok"]
until(lambda: api._sync.status["state"] == "synced", 20)
srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler); dport = srv.server_address[1]
srv.RequestHandlerClass = B.make_handler(api, dport, "tok"); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
APP = f"http://127.0.0.1:{dport}/?t=tok"

errs = []
def watch(pg, who):
    pg.on("pageerror", lambda e: errs.append(f"{who}: {e}"))
    pg.on("console", lambda m: errs.append(f"{who}: {m.text}") if m.type == "error" and not any(x in m.text for x in ("fonts/", "403", "401", "favicon", "ERR_", "Failed to fetch", "WebSocket")) else None)
def A(pg, name, *args): return pg.evaluate("([n,a])=>(window.LF_API||api)(n,...a)", [name, list(args)])
def J(pg, js): return pg.evaluate("()=>{" + js + "}")
def wait(pg, js, t=8000): pg.wait_for_function(js, timeout=t)
def login(pg, user, pw):
    pg.goto(WEB); pg.wait_for_selector("#login.on", timeout=10000)
    pg.fill("#lgUser", user); pg.fill("#lgPass", pw); pg.click("#lgGo"); pg.wait_for_selector("#login.on", state="detached", timeout=10000)
    pg.wait_for_function("document.querySelector('#syncTx').textContent==='Synced'", timeout=20000)
def to_msgs(pg): pg.evaluate("async()=>{await go('msgs')}"); wait(pg, "MX.started&&MX.lastOv>0")
def conv_with(pg, name): return J(pg, f"const c=MX.convs.find(c=>mxTitle(c)==={json.dumps(name)});return c&&c.id")
def last_text(pg): return J(pg, "const m=[...document.querySelectorAll('#mxScroll .mm:not(.pend) .mb')].pop();return m?m.innerText:''")
def type_send(pg, text):
    pg.click("#mxTa"); pg.keyboard.type(text); pg.keyboard.press("Enter")
def msg_el(pg, text): return J(pg, f"const e=[...document.querySelectorAll('#mxScroll .mm')].reverse().find(x=>x.innerText.includes({json.dumps(text)}));return e?e.dataset.mid:null")
def act(pg, mid, sel): pg.evaluate("([m,s])=>{const b=document.querySelector(`#mxScroll .mm[data-mid=\"${m}\"] ${s}`);b.click()}", [mid, sel])

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("LEAFLINE_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"], env=dict(os.environ, USERPROFILE=_BROWSER_HOME) if _BROWSER_HOME else None)
    D = br.new_context(viewport={"width": 1440, "height": 900}).new_page(); watch(D, "gio")
    T = br.new_context(viewport={"width": 1440, "height": 900}).new_page(); watch(T, "tim")
    O = br.new_context(viewport={"width": 1440, "height": 900}).new_page(); watch(O, "omar")
    D.goto(APP); D.wait_for_function("typeof S!=='undefined'&&S.ready&&S.me", timeout=20000)
    login(T, "tim", "Tim123"); login(O, "omar", "Omar123")

    print("1. Messages page and the live connection")
    for pg, who in ((D, "desktop"), (T, "website"), (O, "website")): to_msgs(pg)
    check("Messages is in the sidebar, the dock and the phone menu", J(D, "return !!document.querySelector('.nv[data-go=msgs]')&&!!document.querySelector('.fpill [data-go=msgs]')&&PAGES.some(p=>p[0]==='msgs')"))
    check("live connection (Realtime) is up in the desktop app and on the website", until(lambda: all(J(x, "return MX.live") for x in (D, T, O)), 15))
    check("empty state invites a first message", J(T, "return document.querySelector('#mxList').innerText.includes('No conversations yet')"))

    print("2. direct messages, live delivery, unread, read receipts, typing")
    D.click("#mxNewBtn"); D.wait_for_selector(".mx-pick [data-p]"); D.fill(".ov.on [data-pq]", "Ti"); D.click(f".mx-pick [data-p='{ids['tim']}']")
    wait(D, f"MX.cur&&mxTitle(MX.byId[MX.cur])==='Tim'")
    check("start a direct chat from New message", J(D, "return document.querySelector('#mxHTitle').textContent") == "Tim")
    t0 = time.time(); type_send(D, "Hi Tim, the **Maple** quote is ready")
    wait(D, "!document.querySelector('#mxScroll .mm.pend')&&[...document.querySelectorAll('#mxScroll .mb')].some(b=>b.innerText.includes('Maple'))")
    check("message shows instantly and is confirmed by the database", "Maple" in last_text(D) and J(D, "return document.querySelector('#mxScroll .mb b').textContent") == "Maple")
    check("Tim gets it live, with an unread badge, without refreshing", until(lambda: J(T, "const c=MX.convs.find(c=>mxTitle(c)==='Gio');return c&&c.unread===1&&document.querySelector('#msgBadge').textContent==='1'"), 6))
    print(f"     (delivered to the other person in {time.time() - t0:.1f}s)")
    T.click(f".mx-c[data-cid='{conv_with(T, 'Gio')}']"); wait(T, "[...document.querySelectorAll('#mxScroll .mb')].some(b=>b.innerText.includes('Maple'))")
    check("opening it clears the unread count", until(lambda: J(T, "return MX.byId[MX.cur].unread===0&&document.querySelector('#msgBadge').style.display==='none'"), 5))
    check("Gio sees 'Read' (read receipt)", until(lambda: J(D, "const r=document.querySelector('#mxScroll .mm-rr .mm-st');return r&&r.innerText.startsWith('Read')"), 8))
    T.click("#mxTa"); T.keyboard.type("Thanks, looking")
    check("Gio sees Tim typing", until(lambda: "Tim is typing" in J(D, "return document.querySelector('#mxTyp').innerText"), 8))
    T.keyboard.press("Enter")
    check("Tim's reply arrives live", until(lambda: "looking" in last_text(D), 6))
    check("typing indicator goes away after the message", until(lambda: J(D, "return document.querySelector('#mxTyp').innerText.trim()===''"), 10))

    print("3. replies, reactions, emoji, edit, delete")
    gm = msg_el(T, "Maple"); act(T, gm, "[data-reply]")
    check("reply bar shows who you are replying to", "Replying to" in J(T, "return document.querySelector('.mx-rpl').innerText"))
    type_send(T, "Sending it to them now")
    check("the reply carries a preview of the original", until(lambda: J(D, "const m=[...document.querySelectorAll('#mxScroll .mm')].pop();return m.querySelector('.mm-rp')&&m.querySelector('.mm-rp').innerText.includes('Maple')"), 6))
    D.evaluate("()=>[...document.querySelectorAll('#mxScroll .mm-rp')].pop().click()")
    check("clicking the preview jumps to the original message", until(lambda: J(D, f"return document.querySelector('#mxScroll .mm[data-mid=\"{gm}\"]').classList.contains('flash')"), 4))
    tm = msg_el(D, "Sending it"); act(D, tm, "[data-qr='👍']")
    check("react with 👍", until(lambda: J(D, f"const b=document.querySelector('#mxScroll .mm[data-mid=\"{tm}\"] .mm-rx [data-rx]');return b&&b.innerText.includes('1')&&b.classList.contains('on')"), 5))
    check("Tim sees the reaction live", until(lambda: J(T, f"const b=document.querySelector('#mxScroll .mm[data-mid=\"{tm}\"] .mm-rx [data-rx]');return b&&b.innerText.includes('1')"), 6))
    T.evaluate(f"()=>document.querySelector('#mxScroll .mm[data-mid=\"{tm}\"] .mm-rx [data-rx]').click()")
    check("a second person on the same emoji makes it 2, and hovering names them", until(lambda: J(D, f"const b=document.querySelector('#mxScroll .mm[data-mid=\"{tm}\"] .mm-rx [data-rx]');return b&&b.innerText.includes('2')&&b.title.includes('Tim')"), 6))
    act(D, tm, "[data-qr='👍']")
    check("pressing it again removes only your own", until(lambda: J(T, f"const b=document.querySelector('#mxScroll .mm[data-mid=\"{tm}\"] .mm-rx [data-rx]');return b&&b.innerText.includes('1')&&b.classList.contains('on')"), 6))
    D.click("[data-emo]"); D.wait_for_selector(".mx-emo"); D.fill(".mx-emo input", "rocket"); D.click(".mx-emo .grid [data-e='🚀']")
    check("emoji picker: search and insert into the message", "🚀" in D.input_value("#mxTa"))
    check("...and it is remembered as recently used", J(D, "return getP('emojiRecent',[])[0]") == "🚀")
    D.keyboard.press("Enter")
    check("an emoji-only message shows big", until(lambda: J(D, "return [...document.querySelectorAll('#mxScroll .mb')].pop().classList.contains('only-emoji')"), 6))
    act(D, gm, "[data-edit]"); D.fill("#mxTa", "Hi Tim, the **Maple** quote is ready (v2)"); D.keyboard.press("Enter")
    check("edit your own message; Tim sees the new text and (edited)", until(lambda: J(T, f"const e=document.querySelector('#mxScroll .mm[data-mid=\"{gm}\"] .mb');return e&&e.innerText.includes('(v2)')&&e.innerText.includes('(edited)')"), 6))
    check("there's no edit button on someone else's message", J(D, f"return !document.querySelector('#mxScroll .mm[data-mid=\"{tm}\"] [data-edit]')"))
    rm = msg_el(D, "🚀"); act(D, rm, "[data-del]"); D.click(".ov.on [data-ok]")
    check("delete your own message; it disappears for Tim", until(lambda: J(T, f"const e=document.querySelector('#mxScroll .mm[data-mid=\"{rm}\"]');return e&&e.classList.contains('del')&&e.innerText.includes('deleted')"), 6))

    print("4. group chats")
    D.click("#mxNewBtn"); D.click(".ov.on [data-m='group']"); D.fill("#mxNg", "Sales floor"); D.fill("#mxNd", "Daily wins")
    D.click(f".mx-pick [data-p='{ids['tim']}']"); D.click(f".mx-pick [data-p='{ids['omar']}']")
    check("member chips appear as you pick people", J(D, "return document.querySelectorAll('.ov.on .mx-chips > span').length") == 2)
    D.click(".ov.on [data-ok]"); wait(D, "MX.cur&&MX.byId[MX.cur]&&MX.byId[MX.cur].type==='group'")
    gid = J(D, "return MX.cur")
    check("group created with a 'created the group' line", until(lambda: "created the group" in J(D, "return document.querySelector('#mxScroll').innerText"), 5))
    check("Tim and Omar see the new group live", until(lambda: all(J(x, f"return !!MX.byId['{gid}']") for x in (T, O)), 8))
    check("...and get a 'you were added' notification", until(lambda: any(n["type"] == "member" for n in A(O, "sb_rpc", "msg_notifications", {})["data"]), 6))

    print("5. mentions, @everyone, mute")
    O.click(f".mx-c[data-cid='{gid}']"); wait(O, f"MX.cur==='{gid}'")
    O.click("#mxInfoBtn"); O.wait_for_selector("#mxInfoIn [data-mute]"); O.click("#mxInfoIn [data-mute]")
    check("Omar mutes the group", until(lambda: J(O, f"return MX.byId['{gid}'].muted===true"), 6))
    O.click("#mxInfoBtn"); O.evaluate("async()=>{await go('dash')}")
    D.click("#mxTa"); D.keyboard.type("@Ti")
    check("typing @ opens the people list with online status", until(lambda: J(D, "const m=document.querySelector('.mx-mp');return m&&m.innerText.includes('Tim')&&/Online|Offline/.test(m.innerText)"), 4))
    D.keyboard.press("Enter"); D.keyboard.type("can you check this?")
    check("picking inserts the mention", D.input_value("#mxTa").startswith("@Tim "))
    D.keyboard.press("Enter")
    check("stored as a structured mention (<@user id>), not plain text", until(lambda: any(f"<@{ids['tim']}>" in m["content"] for m in A(D, "sb_rpc", "msg_history", {"p_conv": gid})["data"]), 6))
    check("Tim gets a mention notification and the bell count goes up", until(lambda: J(T, "return MX.notes.some(n=>n.type==='mention')&&document.querySelector('#mxNoteN').textContent!=='0'"), 8))
    check("Tim's sidebar badge turns into the mention colour", until(lambda: J(T, "return document.querySelector('#msgBadge').classList.contains('at')"), 6))
    T.click(f".mx-c[data-cid='{gid}']")
    check("the mention is highlighted for Tim", until(lambda: J(T, "return !!document.querySelector('#mxScroll .mm.atme .ment.me')"), 6))
    T.click("[data-tab=mentions]")
    check("Mentions tab lists it, and clicking opens the message", until(lambda: J(T, "return !!document.querySelector('#mxList [data-jump]')"), 6))
    T.click("#mxList [data-jump]"); T.click("[data-tab=all]")
    type_send(D, "@everyone standup in 5")
    check("@everyone (group owner) notifies members", until(lambda: any(n["type"] == "everyone" for n in A(T, "sb_rpc", "msg_notifications", {})["data"]), 8))
    before = len(A(O, "sb_rpc", "msg_notifications", {})["data"])
    type_send(D, "just a normal update")
    time.sleep(2.5)
    check("muted Omar isn't notified about plain or @everyone messages...", len(A(O, "sb_rpc", "msg_notifications", {})["data"]) == before and not any(n["type"] == "everyone" for n in A(O, "sb_rpc", "msg_notifications", {})["data"]))
    check("...but the messages are still there for him", any("normal update" in m["content"] for m in A(O, "sb_rpc", "msg_history", {"p_conv": gid})["data"]))
    r = A(T, "sb_rpc", "msg_send", {"p_conv": gid, "p_client_op_id": str(uuid.uuid4()), "p_content": "<@everyone> hi", "p_everyone": True})
    check("@everyone is refused for a regular member (enforced by the database)", not r["ok"] and "everyone" in r["error"])

    print("6. pins, files, search")
    O.evaluate("async()=>{await go('msgs')}"); O.click(f".mx-c[data-cid='{gid}']")
    pm = msg_el(T, "standup in 5"); act(T, pm, "[data-pin]")
    check("pin a message; everyone sees the pin", until(lambda: J(O, f"return !!document.querySelector('#mxScroll .mm[data-mid=\"{pm}\"] .mm-pin')"), 8))
    O.click("#mxPinsBtn"); O.wait_for_selector(".mx-pins [data-pj]")
    check("pinned messages list", "standup" in J(O, "return document.querySelector('.mx-pins').innerText"))
    O.click(".mx-pins [data-pj]")
    check("clicking a pin jumps to the message", until(lambda: J(O, f"return document.querySelector('#mxScroll .mm[data-mid=\"{pm}\"]').classList.contains('flash')"), 4))
    D.set_input_files("#mxFile", files=[{"name": "Quote Q4.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 quote"}, {"name": "pic.png", "mimeType": "image/png",
        "buffer": bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e2a1b9f40000000049454e44ae426082")}])
    check("files upload with progress chips, then Send turns on", until(lambda: J(D, "return MX.atts.length===2&&MX.atts.every(a=>a.done)&&!document.querySelector('#mxSend').disabled"), 10))
    D.set_input_files("#mxFile", files=[{"name": "virus.exe", "mimeType": "application/x-msdownload", "buffer": b"MZ"}])
    check("a file type that isn't allowed is refused with a message", J(D, "return MX.atts.length") == 2)
    D.click("#mxSend")
    check("Tim sees the PDF card and the picture", until(lambda: J(T, "return !!document.querySelector('#mxScroll .mm-file')&&!!document.querySelector('#mxScroll .mm-img img[src]')"), 10))
    path = J(T, "return document.querySelector('#mxScroll .mm-file').dataset.dl")
    u = A(T, "sb_storage", "sign", [path])["urls"][path]
    check("Tim can download it through a short-lived private link", requests.get(u).content == b"%PDF-1.4 quote")
    check("shared files list in the group details", (lambda r: any(f["name"] == "Quote Q4.pdf" for f in r["data"]))(A(O, "sb_rpc", "msg_files", {"p_conv": gid})))
    T.fill("#mxQ", "Maple"); T.wait_for_selector("#mxList [data-jump]", timeout=6000)
    check("message search shows sender, chat and time", "Gio" in J(T, "return document.querySelector('#mxList [data-jump]').innerText"))
    T.click("#mxList [data-jump]")
    check("clicking a result opens that chat at the message", until(lambda: J(T, f"return MX.cur&&MX.byId[MX.cur].type==='direct'&&!!document.querySelector('#mxScroll .mm.flash')"), 6))
    T.fill("#mxQ", "Sal")
    check("conversation search filters chats by name", until(lambda: J(T, f"return [...document.querySelectorAll('#mxList [data-cid]')].map(b=>b.dataset.cid).join()==='{gid}'"), 4))
    T.fill("#mxQ", "")

    print("7. privacy (enforced by the database, tried from the page)")
    dm = conv_with(D, "Tim")
    check("Omar can't read Gio and Tim's chat", A(O, "sb_rpc", "msg_history", {"p_conv": dm})["data"] == [])
    r = A(O, "sb_rpc", "msg_send", {"p_conv": dm, "p_client_op_id": str(uuid.uuid4()), "p_content": "sneaky"})
    check("Omar can't post into it", not r["ok"])
    check("the page can only reach messaging functions", A(O, "sb_rpc", "reassign_credit", {})["error"] == "Not allowed." and A(O, "sb_storage", "sign", ["../etc"])["error"] == "Not allowed.")
    D.click(f".mx-c[data-cid='{dm}']"); D.set_input_files("#mxFile", files=[{"name": "private.txt", "mimeType": "text/plain", "buffer": b"secret"}])
    until(lambda: J(D, "return MX.atts.length&&MX.atts.every(a=>a.done)"), 8); D.click("#mxSend")
    until(lambda: J(D, "return !!document.querySelector('#mxScroll .mm-file[data-name=\"private.txt\"]')"), 8)
    ppath = J(D, "return document.querySelector('#mxScroll .mm-file[data-name=\"private.txt\"]').dataset.dl")
    check("Omar can't get a link to a file in a chat he isn't in", A(O, "sb_storage", "sign", [ppath])["urls"].get(ppath) is None)
    check("Omar can't upload into that chat", not A(O, "sb_storage", "sign_upload", [f"{dm}/{ids['omar']}/x.txt"])["ok"])

    print("8. losing the connection")
    F.down = True
    type_send(D, "sent while offline")
    check("shows 'waiting' and keeps the message on this device", until(lambda: J(D, "const p=document.querySelector('#mxScroll .mm.pend');return p&&p.innerText.includes('Waiting')"), 8) and J(D, "return mxOut().length") == 1)
    F.down = False
    check("delivered by itself once the connection is back", until(lambda: J(D, "return mxOut().length===0&&!document.querySelector('#mxScroll .mm.pend')"), 20))
    check("Tim receives it", until(lambda: "sent while offline" in last_text(T) or any("sent while offline" in m["content"] for m in A(T, "sb_rpc", "msg_history", {"p_conv": dm})["data"]), 8))
    check("exactly once (no duplicates from the retries)", sum("sent while offline" in m["content"] for m in A(T, "sb_rpc", "msg_history", {"p_conv": dm, "p_limit": 100})["data"]) == 1)

    print("9. notifications, older messages, second device and phone layout")
    T.evaluate(f"async()=>{{await mxOpen('{gid}');await go('dash')}}")
    for i in range(3): A(D, "sb_rpc", "msg_send", {"p_conv": dm, "p_client_op_id": str(uuid.uuid4()), "p_content": f"ping {i}"})
    T.evaluate("async()=>{await go('msgs')}")
    T.click("#mxNoteBtn"); T.wait_for_selector(".mx-nt .it")
    check("notification list with unread dots", J(T, "return document.querySelectorAll('.mx-nt .it.un').length") >= 1)
    T.click(".mx-nt [data-all]")
    check("mark all as read", until(lambda: J(T, "return MX.notes.every(n=>n.is_read)&&document.querySelector('#mxNoteN').style.display==='none'"), 5))
    T.keyboard.press("Escape")
    for i in range(55): node("/rpc/msg_send", {"p_conv": gid, "p_client_op_id": str(uuid.uuid4()), "p_content": f"history line {i}"}, ids["omar"])
    T.evaluate(f"async()=>{{delete MX.threads['{gid}'];await mxOpen('{gid}')}}")
    check("opening a long chat loads only the newest 40", until(lambda: J(T, f"return MX.threads['{gid}'].list.length===40&&MX.threads['{gid}'].more"), 6))
    T.evaluate("()=>{const s=document.querySelector('#mxScroll');s.scrollTop=0;s.dispatchEvent(new Event('scroll'))}")
    check("scrolling up loads the older ones", until(lambda: J(T, f"return MX.threads['{gid}'].list.length>40"), 6))
    M = br.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True).new_page(); watch(M, "tim-phone")
    login(M, "tim", "Tim123")
    to_msgs(M)
    check("Tim's phone (second device) has the same chats", until(lambda: J(M, f"return !!MX.byId['{gid}']&&!!MX.byId['{dm}']"), 6))
    check("phone shows the list first, no chat panel", J(M, "return getComputedStyle(document.querySelector('#mxChat')).display==='none'"))
    M.tap(f".mx-c[data-cid='{dm}']")
    check("tapping a chat goes full screen and hides the tab bar", until(lambda: J(M, "return document.querySelector('#mx').classList.contains('chat')&&document.body.classList.contains('msg-chat')&&getComputedStyle(document.querySelector('.mx-list')).display==='none'"), 5))
    check("nothing wider than the phone screen", J(M, "return document.documentElement.scrollWidth<=innerWidth&&document.querySelector('#mxComp').getBoundingClientRect().right<=innerWidth"))
    check("message box is 16px so iPhones don't zoom", J(M, "return getComputedStyle(document.querySelector('#mxTa')).fontSize") == "16px")
    D.click(f".mx-c[data-cid='{dm}']"); type_send(D, "hello phone")
    check("a new message reaches the phone live", until(lambda: "hello phone" in last_text(M), 8))
    M.tap("#mxBack")
    check("back returns to the list and the tab bar", until(lambda: J(M, "return !document.body.classList.contains('msg-chat')&&getComputedStyle(document.querySelector('.mx-list')).display!=='none'"), 4))
    check("no unexpected errors in any window", not errs or print("   ", errs[:6]))
    br.close()

print(f"\n{ok} passed, {fail} failed"); sys.stdout.flush()
os._exit(1 if fail else 0)
