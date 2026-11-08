"""Leafline Web Services - Lead Finder v9 backend (runs inside the Electron app, NO API key needed)
Dev run:  pip install requests playwright
          python leafline_backend.py        (prints a local URL to open in a browser)
Electron starts this program, gives it a port and a secret token, and shows its page in a window.
The interface is embedded at the bottom of this file (UI_HTML).
Data:  Google Maps is read through a real (visible) Edge/Chrome window. Each business's own
       website is then scraped for the owner name. Anything not found shows "N/A".
Optional: put Inter-Regular.ttf and Inter-Bold.ttf in a folder called "fonts" next to this file
          (or install Inter in Windows) and the interface uses it automatically.
"""
import calendar, csv, heapq, hmac, html, json, os, queue, random, re, secrets, sqlite3, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, urljoin, urlparse
import requests
import leafline_sync as lsync

BASE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
DATA = os.path.join(os.path.expanduser("~"), "LeaflineLeadFinder")
os.makedirs(DATA, exist_ok=True)
DB = os.path.join(DATA, "leads_v2.db")
PROFILE = os.path.join(DATA, "profile.json")
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
NA = "N/A"
STATUS_LABELS = {"none": "Not called yet", "green": "Called - Meeting set up", "yellow": "Called - Interested",
                 "orange": "Called - No answer", "red": "Called - Not interested"}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------- Google Maps scraping (visible browser, no API key) ----------------
MAX_RESULTS = 120  # Google Maps stops listing around 120 results per search
FEED = 'div[role="feed"]'
FEEDLINK = 'div[role="feed"] a[href*="/maps/place/"]'
JS_SCROLL = "() => { const f = document.querySelector('div[role=\"feed\"]'); if (f) f.scrollTo(0, f.scrollHeight); }"
JS_PLACE = """() => {
  const q = s => document.querySelector(s);
  const at = (el, a) => el ? (el.getAttribute(a) || '') : '';
  const ph = q('button[data-item-id^="phone:tel:"]'), ad = q('button[data-item-id="address"]');
  const web = q('a[data-item-id="authority"]'), f = q('div.F7nice');
  return {phoneLabel: at(ph, 'aria-label'), phoneId: at(ph, 'data-item-id'), addr: at(ad, 'aria-label'),
          site: web ? web.href : '', rate: f ? f.innerText : '',
          star: at(q('span[role="img"][aria-label*="star"]'), 'aria-label'),
          rev: at(q('[aria-label$="reviews"], [aria-label$="review"]'), 'aria-label')};
}"""
# Opening-hours table: one row per weekday (the page is requested in English with ?hl=en)
JS_HOURS = r"""() => {
  const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], out = {};
  document.querySelectorAll('table tr').forEach(tr => {
    const c = tr.querySelectorAll('td'); if (c.length < 2) return;
    const d = days.find(x => (c[0].textContent || '').trim().startsWith(x)); if (!d) return;
    const li = Array.from(c[1].querySelectorAll('li')).map(x => (x.textContent || '').trim()).filter(Boolean);
    let t = li.length ? li.join(', ') : (c[1].textContent || '');
    t = t.replace(/\s+/g, ' ').trim() || c[1].getAttribute('aria-label') || '';
    if (t) out[d] = t.trim();
  });
  return out;
}"""
HOURS_BTN = '[data-item-id="oh"], [aria-label*="open hours" i]'


def place_id(href):
    m = re.search(r"0x[0-9a-f]+:0x[0-9a-f]+", href)
    return m.group(0) if m else href.split("?")[0]


def parse_rating(rate, star, rev):
    m = re.search(r"([0-5][.,]\d)", rate or "") or re.search(r"([0-5][.,]\d|[0-5]) star", star or "")
    rating = m.group(1).replace(",", ".") if m else NA
    m2 = re.search(r"\(([\d,.\s]+)\)", rate or "") or re.search(r"([\d,]+)\s+review", rev or "", re.I)
    reviews = re.sub(r"\D", "", m2.group(1)) if m2 else ""
    return rating, reviews or NA


def parse_place(name, d):
    ph = re.sub(r"[^\d+()\-\s.]", "", (d.get("phoneLabel") or "").replace("Phone:", "")).strip()
    if len(re.sub(r"\D", "", ph)) < 7:
        ph = re.sub(r"[^\d+]", "", (d.get("phoneId") or "").replace("phone:tel:", ""))
    if len(re.sub(r"\D", "", ph)) < 7:
        return None
    rating, reviews = parse_rating(d.get("rate"), d.get("star"), d.get("rev"))
    return dict(name=name, phone=ph, address=(d.get("addr") or "").replace("Address:", "").strip() or NA,
                website=d.get("site") or NA, rating=rating, reviews=reviews)


def clean_hours(h):
    """Weekday -> text, with odd Google spaces normalised. Returns a JSON string ('' if nothing usable)."""
    out = {}
    for k, v in (h or {}).items():
        if k in DAYS and isinstance(v, str):
            t = re.sub(r"[\u202f\u00a0\u2009\u2007]", " ", v)
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                out[k] = t
    return json.dumps(out, ensure_ascii=False) if out else ""


def read_hours(page):
    h = page.evaluate(JS_HOURS)
    if h:
        return h
    try:
        btn = page.locator(HOURS_BTN)
        if btn.count():  # the table is usually only in the page after the hours row is opened
            btn.first.click(timeout=1500)
            try:
                page.wait_for_selector("table tr td", timeout=1500, state="attached")
            except Exception:
                pass
            h = page.evaluate(JS_HOURS)
    except Exception:
        pass
    return h or {}


def launch(p):
    args = ["--lang=en-US", "--disable-blink-features=AutomationControlled"]
    for ch in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=ch, headless=False, args=args) if ch else p.chromium.launch(headless=False, args=args)
        except Exception:
            continue
    raise RuntimeError("Couldn't open a browser. Install Microsoft Edge or Google Chrome and try again.")


def guard(page, say):
    if "consent.google" in page.url:
        try:
            page.locator('button:has-text("Accept all"), button:has-text("Reject all")').first.click(timeout=8000)
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
    if "/sorry" in page.url:
        say("Google wants you to verify you're human - solve it in the browser window, then wait...")
        page.wait_for_url(lambda u: "/sorry" not in u, timeout=240000)


def gmaps_scrape(q, limit, say, stop):
    """Generator: yields one dict per Google Maps business that has a phone number.
    say(text, fraction=None) reports progress (fraction 0..1 of the whole progress bar)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Missing package. In the terminal run:  pip install playwright")
    with sync_playwright() as p:
        browser = launch(p)
        try:
            ctx = browser.new_context(locale="en-US", viewport={"width": 1250, "height": 850})
            ctx.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "media", "font") else r.continue_())
            page = ctx.new_page()
            page.goto("https://www.google.com/maps/search/" + quote_plus(q) + "?hl=en", wait_until="domcontentloaded", timeout=45000)
            guard(page, say)
            try:
                page.wait_for_selector(FEED, timeout=20000)
            except Exception:
                raise RuntimeError("Google Maps showed no list of results for that search. Try different wording or a broader area.")
            items, prev, stale = {}, -1, 0
            for _ in range(80):  # scroll the results list until the end
                for href, name in page.eval_on_selector_all(FEEDLINK, "els => els.map(e => [e.href, e.getAttribute('aria-label') || ''])"):
                    items.setdefault(place_id(href), (href, name))
                say(f"Collecting listings... {len(items)} found", 0.2 * min(1.0, len(items) / limit))
                if len(items) >= limit or stop.is_set():
                    break
                stale = stale + 1 if len(items) == prev else 0
                if stale >= 4 or page.get_by_text(re.compile(r"reached the end", re.I)).count():
                    break
                prev = len(items)
                page.evaluate(JS_SCROLL)
                page.wait_for_timeout(1300)
            todo = list(items.values())[:limit]
            for i, (href, name) in enumerate(todo, 1):
                if stop.is_set():
                    break
                say(f"Reading listing {i}/{len(todo)}: {name}", 0.2 + 0.7 * (i - 1) / len(todo))
                try:
                    page.goto(href, wait_until="domcontentloaded", timeout=30000)
                    guard(page, say)
                    try:
                        page.wait_for_selector('button[data-item-id^="phone:tel:"], a[data-item-id="authority"], button[data-item-id="address"]', timeout=7000)
                    except Exception:
                        pass
                    lead = parse_place(name, page.evaluate(JS_PLACE))
                    if lead:
                        lead["hours"] = clean_hours(read_hours(page))
                except Exception:
                    continue
                if lead:
                    lead["id"] = place_id(href)
                    yield lead
                page.wait_for_timeout(random.randint(300, 800))
        finally:
            browser.close()


# ---------------- website scraping: owner / rating ----------------
_NAME = r"[A-Z][a-z]{1,15}(?: [A-Z]\.)? [A-Z][A-Za-z'’\-]{1,20}"
_ROLE = r"owner|co-owner|founder|co-founder|proprietor|president|ceo"
P1 = re.compile(r"\b(?i:owned(?: and operated)? by|founded by|(?:%s)(?: is|:|,|-|–|—)?)\s+(%s)" % (_ROLE, _NAME))
P2 = re.compile(r"(%s)\s*(?:,|\||-|–|—|\()\s*(?i:%s)\b" % (_NAME, _ROLE))
BAD = set("""Owner Operated Business Services Service Company Inc Ltd Our Team The And Contact Us About Home Page Read
More Family Local Licensed Insured Proudly Canada Ontario Toronto Construction Renovations Renovation Contracting Group
Solutions Design Designs Homes Quality Professional Free Estimate Estimates Call Today Get Quote Welcome Meet Learn
Operator Manager Director Customer Support Info Privacy Policy Terms Home Improvement Kitchen Bathroom Basement""".split())


def find_owner(text):
    for p in (P1, P2):
        for m in p.finditer(text):
            n = m.group(1).strip()
            if not any(w.strip(".") in BAD for w in n.split()):
                return n
    return NA


def find_rating(raw):
    r = re.search(r'"ratingValue"\s*:\s*"?([0-5](?:\.\d+)?)', raw)
    c = re.search(r'"(?:reviewCount|ratingCount)"\s*:\s*"?(\d+)', raw)
    return (r.group(1) if r else NA, c.group(1) if c else NA)


def fetch(url):
    try:
        r = requests.get(url, headers=BROWSER, timeout=7)
        if r.ok and "html" in r.headers.get("content-type", "html"):
            return r.text[:400000]
    except Exception:
        pass
    return ""


def enrich(site):
    base = site if site.lower().startswith("http") else "http://" + site
    pages = [fetch(base)]
    extra = []
    for m in re.finditer(r'href=["\']([^"\'#]+)["\']', pages[0], re.I):
        h = m.group(1)
        if re.search(r"contact|about|team|story|meet", h, re.I) and not h.lower().startswith(("mailto:", "tel:", "javascript:")):
            u = urljoin(base, h)
            if urlparse(u).netloc == urlparse(base).netloc and u not in extra and u != base:
                extra.append(u)
    pages += [fetch(u) for u in extra[:2]]
    raw = " ".join(pages)
    txt = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", raw)
    txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", txt)))
    rating, reviews = find_rating(raw)
    return find_owner(txt), rating, reviews


# ---------------- opening hours -> "open now?" ----------------
_T = r"\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?"
RANGE = re.compile(r"(%s)\s*-\s*(%s)" % (_T, _T))


def _tok(s):
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap])?", s.strip())
    return int(m.group(1)), int(m.group(2) or 0), m.group(3)


def _mins(h, m, ap):
    if ap:
        h = h % 12 + (12 if ap == "p" else 0)
    return h * 60 + m


def norm_hours_text(txt):
    t = re.sub(r"[\u202f\u00a0\u2009\u2007]", " ", txt or "")
    t = re.sub(r"[\u2013\u2014\u2012]", "-", t)
    t = re.sub(r"\s+(?:to|until)\s+", "-", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def parse_ranges(txt):
    """'9 am-5 pm, 6-9 pm' -> [(540, 1020), (1080, 1260)]. Overnight ranges end past 1440. Closed -> []."""
    t = norm_hours_text(txt).lower()
    if "24 hours" in t or "open 24" in t:
        return [(0, 1440)]
    out = []
    for a, b in RANGE.findall(t):
        h1, m1, ap1 = _tok(a)
        h2, m2, ap2 = _tok(b)
        end = _mins(h2, m2, ap2)
        start = _mins(h1, m1, ap1 or ap2)
        if not ap1 and ap2 and start > end:  # '9-5 pm' means 9 am to 5 pm
            start -= 720
        if end <= start:
            end += 1440
        out.append((start, end))
    return out


def fmt_min(m):
    m %= 1440
    h, mm = divmod(m, 60)
    return f"{h % 12 or 12}:{mm:02d} {'am' if h < 12 else 'pm'}" if mm else f"{h % 12 or 12} {'am' if h < 12 else 'pm'}"


def open_status(hours_json, now=None):
    """-> (state, today_text, note). state: 'open' | 'closed' | 'unknown'. Uses this computer's clock."""
    now = now or datetime.now()
    try:
        h = json.loads(hours_json) if hours_json else {}
    except ValueError:
        h = {}
    today = h.get(DAYS[now.weekday()]) if isinstance(h, dict) else None
    if not today:
        return "unknown", NA, ""
    ranges = parse_ranges(today)
    closed_word = "closed" in today.lower() and not ranges
    label = "Closed" if closed_word else (norm_hours_text(today).replace("-", "\u2013") if ranges else norm_hours_text(today))
    if not ranges and not closed_word:
        return "unknown", label, ""
    mins = now.hour * 60 + now.minute
    prev = h.get(DAYS[now.weekday() - 1]) or ""  # an overnight range from yesterday may still be running
    spill = [b - 1440 for a, b in parse_ranges(prev) if b > 1440]
    left = [b - mins for a, b in ranges if a <= mins < b] + [s - mins for s in spill if mins < s]
    if left:
        if closed_word and spill:  # today says Closed but yesterday's overnight shift is still running
            label = "Until " + fmt_min(max(spill))
        m = min(left)
        return "open", label, (f"Closes in {m} min" if m <= 60 else "")
    later = [a for a, b in ranges if a > mins]
    return "closed", label, (f"Opens {fmt_min(min(later))}" if later else "")


# ---------------- database ----------------
def norm_type(t):
    """'car wrapping ' -> 'Car Wrapping' (keeps words like HVAC as typed)."""
    return " ".join(w[:1].upper() + w[1:] for w in (t or "").split()) or "Other"


def open_db(path):
    db = sqlite3.connect(path, check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY, name TEXT, phone TEXT, pdigits TEXT DEFAULT '',
        btype TEXT DEFAULT '', owner TEXT DEFAULT 'N/A', rating TEXT DEFAULT 'N/A', reviews TEXT DEFAULT 'N/A',
        website TEXT DEFAULT 'N/A', address TEXT DEFAULT 'N/A', search TEXT, status TEXT DEFAULT 'none',
        notes TEXT DEFAULT '', called_at TEXT, enriched INTEGER DEFAULT 0, hours TEXT DEFAULT '', added_at TEXT DEFAULT '', meeting_at TEXT DEFAULT '')""")
    cols = {r[1] for r in db.execute("PRAGMA table_info(leads)")}
    for c in ("pdigits", "btype", "hours", "added_at", "meeting_at"):  # upgrade older databases in place
        if c not in cols:
            db.execute(f"ALTER TABLE leads ADD COLUMN {c} TEXT DEFAULT ''")
    for id_, ph in db.execute("SELECT id,phone FROM leads WHERE pdigits IS NULL OR pdigits=''").fetchall():
        db.execute("UPDATE leads SET pdigits=? WHERE id=?", (re.sub(r"\D", "", ph or "")[-10:], id_))
    for id_, srch in db.execute("SELECT id,search FROM leads WHERE btype IS NULL OR btype=''").fetchall():
        bt = norm_type(srch.split("|")[0]) if srch and "|" in srch else "Other"  # searches are stored as "type | area"
        db.execute("UPDATE leads SET btype=? WHERE id=?", (bt, id_))
    db.execute("UPDATE leads SET added_at=COALESCE(called_at, ?) WHERE added_at IS NULL OR added_at=''",
               (datetime.now().strftime("%Y-%m-%d %H:%M"),))
    db.execute("""CREATE TABLE IF NOT EXISTS deals(id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT NOT NULL,
        upfront REAL DEFAULT 0, monthly REAL DEFAULT 0, months INTEGER DEFAULT 0, closed_at TEXT DEFAULT '',
        first_bill TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TEXT DEFAULT '')""")
    if "confirmed" not in {r[1] for r in db.execute("PRAGMA table_info(deals)")}:
        db.execute("ALTER TABLE deals ADD COLUMN confirmed TEXT DEFAULT ''")     # payments someone ticked as really received
    db.execute("""CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, day TEXT DEFAULT '',
        start_time TEXT DEFAULT '', color TEXT DEFAULT '', icon TEXT DEFAULT '', repeat_kind TEXT DEFAULT 'none', until TEXT DEFAULT '',
        notes TEXT DEFAULT '', lead_id TEXT DEFAULT '', created_at TEXT DEFAULT '')""")
    db.commit()
    return db


LEAD_COLS = "id,name,btype,phone,owner,rating,reviews,address,website,notes,status,called_at,hours,search,meeting_at"


def lead_dict(r, now=None):
    st, today, note = open_status(r[12], now)
    return dict(id=r[0], name=r[1] or "", btype=r[2] or "Other", phone=r[3] or "", owner=r[4] or NA, rating=r[5] or NA,
                reviews=r[6] or NA, address=r[7] or NA, website=r[8] or NA, notes=r[9] or "", status=r[10] or "none",
                called_at=r[11] or "", open=st, hours=today, open_note=note, search=r[13] or "", meeting_at=r[14] or "")


# ---------------- deals / profits (every amount is typed in by hand) ----------------
DEAL_COLS = "id,client,upfront,monthly,months,closed_at,first_bill,notes,confirmed"


def parse_day(v):
    try:
        return datetime.strptime(str(v or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def add_months(d, n, anchor):
    """Same day of the month, n months later. Short months use their last day (Jan 31 -> Feb 28)."""
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return date(y, m + 1, min(anchor, calendar.monthrange(y, m + 1)[1]))


def money(x):
    return round(float(x), 2)


def deal_dict(r):
    return dict(id=r[0], client=r[1] or "", upfront=r[2] or 0.0, monthly=r[3] or 0.0, months=r[4] or 0,
                closed_at=r[5] or "", first_bill=r[6] or r[5] or "", notes=r[7] or "", confirmed=conf_set(r[8] if len(r) > 8 else ""))


def conf_set(v):
    """The payments of a deal that were ticked as really received, as a set of "YYYY-MM-DD:kind" keys."""
    return {k for k in str(v or "").split(",") if re.fullmatch(r"\d{4}-\d{2}-\d{2}:(upfront|monthly)", k)}


def pay_key(dt, kind):
    return f"{dt.isoformat()}:{kind}"


def is_confirmed(d, dt, kind):
    return pay_key(dt, kind) in d.get("confirmed", ())


def deal_payments(d):
    """Every payment of one deal, oldest first, as (date, amount, kind).
    A deal with months = 0 and a monthly amount never ends, so every caller must stop at a date."""
    closed = parse_day(d["closed_at"])
    first = parse_day(d["first_bill"]) or closed
    up = [(closed, d["upfront"], "upfront")] if closed and d["upfront"] > 0 else []

    def monthly():
        k = 0
        while first and d["monthly"] > 0 and (d["months"] == 0 or k < d["months"]):
            yield (add_months(first, k, first.day), d["monthly"], "monthly")
            k += 1
    return heapq.merge(up, monthly(), key=lambda p: p[0])


def payments_between(d, lo, hi):
    out = []
    for p in deal_payments(d):
        if p[0] > hi:
            break
        if p[0] >= lo:
            out.append(p)
    return out


def deal_summary(d, today):
    """Money received (only payments someone confirmed), payments whose date passed but nobody confirmed yet,
    money still to come, and the next payment."""
    got = left = waiting = 0.0
    n_wait = 0
    nxt = None
    ongoing = d["monthly"] > 0 and d["months"] == 0
    for dt, amt, kind in deal_payments(d):
        if dt <= today:
            if is_confirmed(d, dt, kind):
                got += amt
            else:
                waiting += amt; n_wait += 1
            continue
        if nxt is None:
            nxt = (dt, amt)
        if ongoing:
            break
        left += amt
    return dict(collected=money(got), unconfirmed=money(waiting), unconfirmed_count=n_wait, remaining=None if ongoing else money(left), ongoing=ongoing,
                next_date=nxt[0].isoformat() if nxt else "", next_amount=money(nxt[1]) if nxt else 0.0)


def clean_deal(d):
    """Returns (clean deal, "") or (None, message for the user)."""
    if not isinstance(d, dict):
        return None, "Nothing to save."
    client = str(d.get("client") or "").strip()[:80]
    if not client:
        return None, "Type the client's name."
    amt = {}
    for k, label in (("upfront", "Upfront amount"), ("monthly", "Monthly amount")):
        raw = str(d.get(k) if d.get(k) is not None else "").replace("$", "").replace(",", "").strip()
        try:
            v = float(raw) if raw else 0.0
        except ValueError:
            return None, f"{label} must be a number."
        if not 0 <= v <= 10_000_000:
            return None, f"{label} must be between 0 and 10,000,000."
        amt[k] = money(v)
    if amt["upfront"] <= 0 and amt["monthly"] <= 0:
        return None, "Enter an upfront amount, a monthly amount, or both."
    raw = str(d.get("months") if d.get("months") is not None else "").strip()
    try:
        months = float(raw) if raw else 0.0
        if months != int(months) or not 0 <= months <= 600:
            raise ValueError
    except (ValueError, OverflowError):
        return None, "Number of months must be a whole number from 1 to 600 (leave it empty if there is no end date)."
    closed = parse_day(d.get("closed_at"))
    if not closed:
        return None, "Pick the date the deal was closed."
    first = parse_day(d.get("first_bill")) or closed
    return dict(client=client, upfront=amt["upfront"], monthly=amt["monthly"], months=int(months) if amt["monthly"] > 0 else 0,
                closed_at=closed.isoformat(), first_bill=first.isoformat(), notes=str(d.get("notes") or "").strip()[:500]), ""


# ---------------- calendar events (typed in by hand; meetings, payments and closed deals are read from the rest of the app) ----------------
EVENT_COLS = "id,title,day,start_time,color,icon,repeat_kind,until,notes,lead_id,assigned_to,created_by,done"
EVENT_COLORS = ("#3DDC84", "#4DD0E1", "#5C9DFF", "#B388FF", "#FF7EB6", "#FF5C5C", "#FF9F43", "#FFD60A", "#C6F04A", "#B8C4BC")
EVENT_ICONS = ("cal", "users", "phone", "video", "coffee", "briefcase", "dollar", "gift", "star", "flag", "heart", "bolt",
               "pin", "mail", "clock", "trophy", "bell", "check")
REPEATS = ("none", "daily", "weekly", "monthly", "yearly")


def event_dict(r):
    return dict(id=r[0], title=r[1] or "", date=r[2] or "", time=r[3] or "", color=r[4] or EVENT_COLORS[0], icon=r[5] or EVENT_ICONS[0],
                repeat=r[6] or "none", until=r[7] or "", notes=r[8] or "", lead_id=r[9] or "",
                assigned_to=r[10] or "" if len(r) > 10 else "", created_by=r[11] or "" if len(r) > 11 else "",
                done=bool(r[12]) if len(r) > 12 else False)


def event_dates(e, lo, hi):
    """Every date of one event inside [lo, hi]. Repeating events never end by themselves, so this stops at hi."""
    start = parse_day(e["date"])
    if not start:
        return
    until = parse_day(e["until"]) if e["until"] else None
    end = min(hi, until) if until else hi
    rep = e["repeat"]
    if rep == "none":
        if lo <= start <= end:
            yield start
        return
    if rep in ("daily", "weekly"):
        step = 1 if rep == "daily" else 7
        d = start + timedelta(days=max(0, (lo - start).days // step) * step)
        while d <= end:
            if d >= lo:
                yield d
            d += timedelta(days=step)
        return
    per = 1 if rep == "monthly" else 12
    k = max(0, ((lo.year - start.year) * 12 + lo.month - start.month) // per - 1)
    while True:
        d = add_months(start, k * per, start.day)
        if d > end:
            return
        if d >= lo:
            yield d
        k += 1


def clean_event(d):
    """Returns (clean event, "") or (None, message for the user)."""
    if not isinstance(d, dict):
        return None, "Nothing to save."
    title = str(d.get("title") or "").strip()[:80]
    if not title:
        return None, "Type a title for the event."
    day = parse_day(d.get("date"))
    if not day:
        return None, "Pick a date for the event."
    t = str(d.get("time") or "").strip()
    if t:
        try:
            t = datetime.strptime(t[:5], "%H:%M").strftime("%H:%M")
        except ValueError:
            return None, "The time must look like 14:30 (leave it empty for an all-day event)."
    rep = str(d.get("repeat") or "none")
    if rep not in REPEATS:
        return None, "Pick how often the event repeats."
    raw_until = str(d.get("until") or "").strip()
    until = parse_day(raw_until) if raw_until else None
    if raw_until and not until:
        return None, "The repeat-until date is not valid."
    if until and until < day:
        return None, "The repeat-until date can't be before the event date."
    color = d.get("color") if d.get("color") in EVENT_COLORS else EVENT_COLORS[0]
    icon = d.get("icon") if d.get("icon") in EVENT_ICONS else EVENT_ICONS[0]
    return dict(title=title, day=day.isoformat(), start_time=t, color=color, icon=icon, repeat=rep,
                until=until.isoformat() if until and rep != "none" else "", notes=str(d.get("notes") or "").strip()[:500],
                lead_id=str(d.get("lead_id") or "").strip()[:200]), ""


# ---------------- account profile (cosmetic, stored on this PC only) ----------------
COLORS = ("#3DDC84", "#5EE6B8", "#FFD60A", "#FF9F43", "#F2788A", "#7FB6FF")
PROFILE_DEFAULT = dict(name="", email="", phone="", company="Leafline Web Services", role="", color=COLORS[0],
                       goal=25, country="Canada", max_results=MAX_RESULTS)


def load_profile(path=PROFILE):
    p = dict(PROFILE_DEFAULT)
    try:
        with open(path, encoding="utf-8") as fh:
            p = clean_profile(json.load(fh), p)
    except (OSError, ValueError):
        pass
    return p


def clean_profile(d, cur):
    out = dict(cur)
    if not isinstance(d, dict):
        return out
    for k in ("name", "email", "phone", "company", "role", "country"):
        if k in d:
            out[k] = str(d[k] if d[k] is not None else "").strip()[:80]
    if d.get("color") in COLORS:
        out["color"] = d["color"]
    for k, lo, hi in (("goal", 1, 500), ("max_results", 10, 120)):
        if k in d:
            try:
                out[k] = max(lo, min(hi, int(d[k])))
            except (TypeError, ValueError):
                pass
    return out


# ---------------- API used by the interface ----------------
# ---------------- script sanitiser: scripts are shared, so the HTML is cleaned here as well as in the page ----------------
from html.parser import HTMLParser as _HP

_OK_TAGS = {"p", "div", "br", "b", "strong", "i", "em", "u", "s", "strike", "del", "span", "font", "ul", "ol", "li", "h1", "h2", "h3",
            "blockquote", "a", "hr", "sub", "sup", "mark"}
_OK_STYLE = {"color", "background-color", "font-size", "font-family", "font-weight", "font-style", "text-decoration", "text-align",
             "line-height", "margin-left", "text-indent"}


def _clean_style(v):
    out = []
    for part in str(v or "").split(";"):
        if ":" not in part:
            continue
        k, val = (x.strip() for x in part.split(":", 1))
        k = k.lower()
        if k in _OK_STYLE and not re.search(r"url\(|expression|javascript|@import|[<>{}]", val, re.I) and len(val) < 120:
            out.append(f"{k}:{val}")
    return ";".join(out)


class _San(_HP):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.o, self.skip, self.stack = [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object", "embed", "svg", "math"):
            self.skip += 1
            self.stack.append(None)
            return
        if self.skip or tag not in _OK_TAGS:
            return
        a = dict(attrs)
        keep = ""
        st = _clean_style(a.get("style"))
        if st:
            keep += f' style="{html.escape(st, quote=True)}"'
        if tag == "font":
            if re.fullmatch(r"[1-7]", a.get("size") or ""):
                keep += f' size="{a["size"]}"'
            if re.fullmatch(r"#?[0-9a-fA-F]{3,8}|[a-zA-Z]{3,20}", a.get("color") or ""):
                keep += f' color="{html.escape(a["color"], quote=True)}"'
        if tag == "a":
            h = (a.get("href") or "").strip()
            if re.match(r"(https?://|mailto:|tel:)", h, re.I):
                keep += f' href="{html.escape(h, quote=True)}" target="_blank" rel="noopener noreferrer"'
        if tag in ("br", "hr"):
            self.o.append(f"<{tag}>")
            return
        self.o.append(f"<{tag}{keep}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object", "embed", "svg", "math"):
            if self.skip:
                self.skip -= 1
            return
        if not self.skip and tag in _OK_TAGS and tag not in ("br", "hr"):
            self.o.append(f"</{tag}>")

    def handle_data(self, d):
        if not self.skip:
            self.o.append(html.escape(d, quote=False))


def sanitize_html(s):
    p = _San()
    try:
        p.feed(str(s or ""))
        p.close()
    except Exception:
        return html.escape(re.sub(r"<[^>]*>", "", str(s or "")), quote=False)
    return "".join(p.o)


class Api:
    """Every name in API_METHODS is callable from the page as POST /api/<name> (JSON list of arguments).
    Events for the page (progress, new leads...) are pushed to every open /events stream."""

    def __init__(self, db=None, profile_path=PROFILE):
        self._db = db or open_db(DB)
        self._lock = threading.RLock()
        self._profile_path = profile_path
        self._profile = load_profile(profile_path)
        self._subs = []
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._busy = False
        self._q, self._bt, self._current = "", "Other", None
        self._n = self._skipped = 0
        self._sync = lsync.Sync(self._db, self._lock, self._emit, os.path.dirname(profile_path) or DATA)
        self._sync.start()

    # ----- plumbing -----
    def _emit(self, ev, data=None):
        if not self._ready.is_set():
            return
        msg = json.dumps({"e": ev, "d": data if data is not None else {}})
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            q.put(msg)

    def _say(self, text, frac=None):
        self._emit("progress", {"text": text, "frac": frac})

    def _on_closing(self):
        self._stop.set()

    def _rows(self, where, args=(), order=""):
        with self._lock:
            return self._db.execute(f"SELECT {LEAD_COLS} FROM leads WHERE {where} {order}", args).fetchall()

    # ----- startup / account -----
    def boot(self):
        self._ready.set()
        if not getattr(self, "_restored", False):
            self._restored = True
            try: self._sync.restore()
            except Exception: pass
        return dict(profile=self._profile, stats=self.stats(), find=self.get_find("current" if self._current else "all"),
                    called=self.get_called(), current=self._current, running=self._busy, db_path=DB, deals=self.get_deals(),
                    auth=dict(me=self._sync.me(), sync=self._sync.status, people=self._sync.people()))

    # ----- accounts and sync (Supabase) -----
    def sign_in(self, username, password):
        try:
            me = self._sync.sign_in(str(username or ""), str(password or ""))
        except lsync.AuthFail as e:
            return dict(ok=False, error=str(e))
        except lsync.Offline:
            return dict(ok=False, error="Can't reach the Leafline server. Check your internet connection and try again.")
        except Exception as e:
            return dict(ok=False, error="Sign-in failed: " + str(e)[:120])
        return dict(ok=True, me=me)

    def sign_out(self):
        return self._sync.sign_out()

    def set_avatar(self, data_url=""):
        d = str(data_url or "")
        if d and not re.match(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$", d):
            return dict(ok=False, error="That doesn't look like a picture.")
        if len(d) > 60000:
            return dict(ok=False, error="That picture is too large.")
        if not self._uid():
            return dict(ok=False, error="Sign in first.")
        self._sync.set_avatar(d)
        return dict(ok=True, shared=bool(self._sync.caps.get("avatar")))

    def set_profile_ext(self, d):
        """Title, bio, mood, accent colour, thought of the day and banner picture (shown to the whole team)."""
        d = d if isinstance(d, dict) else {}
        if not self._uid():
            return dict(ok=False, error="Sign in first.")
        out = {}
        lim = dict(title=40, bio=280, thought=140, mood=8)
        for k, n in lim.items():
            if k in d:
                out[k] = " ".join(str(d[k] or "").split())[:n] if k != "bio" else "\n".join(l.strip() for l in str(d[k] or "").strip().splitlines())[:n]
        if "accent" in d:
            a = str(d["accent"] or "")
            if a and not re.match(r"^#[0-9A-Fa-f]{6}$", a):
                return dict(ok=False, error="Pick a colour from the list.")
            out["accent"] = a
        if "banner" in d:
            b = str(d["banner"] or "")
            if b and not re.match(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$", b):
                return dict(ok=False, error="That doesn't look like a picture.")
            if len(b) > 150000:
                return dict(ok=False, error="That banner is too large.")
            out["banner"] = b
        self._sync.set_ext(out)
        return dict(ok=True, shared=bool(self._sync.caps.get("pext")), ext=self._sync.ext())

    # ----- animated pictures (migration 5), leaderboard and the announcements board -----
    @staticmethod
    def sniff_image(raw):
        """Trust the bytes, not the file name: only real GIF/PNG/JPEG/WebP/AVIF files are accepted."""
        if raw[:6] in (b"GIF87a", b"GIF89a"): return "image/gif"
        if raw[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
        if raw[:3] == b"\xff\xd8\xff": return "image/jpeg"
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP": return "image/webp"
        if raw[4:8] == b"ftyp" and raw[8:12] in (b"avif", b"avis"): return "image/avif"
        return None

    def upload_media(self, kind, data_url, thumb=""):
        if kind not in ("avatar", "banner"): return dict(ok=False)
        if not self._uid(): return dict(ok=False, error="Sign in first.")
        m = re.match(r"^data:[\w/+.-]*;base64,([A-Za-z0-9+/=]+)$", str(data_url or ""))
        if not m: return dict(ok=False, error="That doesn't look like a picture.")
        import base64 as _b64
        try: raw = _b64.b64decode(m.group(1), validate=True)
        except ValueError: return dict(ok=False, error="That picture is damaged.")
        if len(raw) > 8 * 1024 * 1024: return dict(ok=False, error="That file is over 8 MB. Pick a smaller one.")
        mime = self.sniff_image(raw)
        if not mime: return dict(ok=False, error="Use a GIF, WebP, PNG, JPEG or AVIF image.")
        t = str(thumb or "")
        if t and (not re.match(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$", t) or len(t) > (60000 if kind == "avatar" else 150000)): t = ""
        try:
            return self._sync.upload_media(kind, raw, mime, t or None)
        except lsync.Offline:
            return dict(ok=False, error="You're offline. Pictures upload when you're connected.")
        except Exception as e:
            return dict(ok=False, error="Upload failed: " + str(e)[:140])

    def clear_media(self, kind):
        if kind not in ("avatar", "banner"): return dict(ok=False)
        try: return self._sync.clear_media(kind)
        except lsync.Offline: return dict(ok=False, error="You're offline.")
        except Exception as e: return dict(ok=False, error=str(e)[:140])

    def set_banner_pos(self, n):
        try: n = max(0, min(100, int(n)))
        except (TypeError, ValueError): return dict(ok=False)
        try: return self._sync.set_banner_pos(n)
        except lsync.Offline: return dict(ok=True, pending=True)
        except Exception as e: return dict(ok=False, error=str(e)[:140])

    def get_board(self):
        if not self._uid(): return dict(ok=False, error="Sign in first.")
        try: return self._sync.board()
        except Exception as e: return dict(ok=False, error=str(e)[:160])

    def get_posts(self):
        if not self._uid(): return dict(ok=False, error="Sign in first.")
        try: return self._sync.posts()
        except lsync.Offline: return dict(ok=False, offline=True, error="You're offline. The board loads when you reconnect.")
        except Exception as e: return dict(ok=False, error=str(e)[:160])

    def save_post(self, d):
        d = d if isinstance(d, dict) else {}
        title = " ".join(str(d.get("title") or "").split())[:120]
        body = str(d.get("body") or "").strip()[:4000]
        kind = d.get("kind") if d.get("kind") in ("announcement", "idea", "update") else "announcement"
        if not title: return dict(ok=False, error="Give the post a title.")
        try: return self._sync.save_post(dict(id=str(d.get("id") or ""), title=title, body=body, kind=kind))
        except lsync.Offline: return dict(ok=False, error="You're offline. Try again when you're connected.")
        except Exception as e: return dict(ok=False, error="Couldn't save: " + str(e)[:140])

    def post_op(self, op, pid, arg=None):
        if op not in ("delete", "pin", "react", "comment", "uncomment", "recomment") or not re.match(r"^[0-9a-f-]{36}$", str(pid or "")):
            return dict(ok=False)
        if op == "react" and arg not in ("👍", "🔥", "💡", "🎉", "❤️"): return dict(ok=False)
        if op in ("comment", "recomment"):
            arg = str(arg or "").strip()[:1000]
            if not arg: return dict(ok=False, error="Write something first.")
        try: return self._sync.post_op(op, str(pid), arg)
        except lsync.Offline: return dict(ok=False, error="You're offline.")
        except Exception as e: return dict(ok=False, error=str(e)[:140])

    def get_credit(self, kind, id):
        if kind not in ("lead", "deal"): return dict(ok=False)
        try: return dict(ok=True, owner=self._sync.get_credit(kind, str(id)))
        except lsync.Offline: return dict(ok=False, error="You're offline.")
        except Exception as e: return dict(ok=False, error=str(e)[:140])

    def set_credit(self, kind, id, to):
        if kind not in ("lead", "deal") or not re.match(r"^[0-9a-f-]{36}$", str(to or "")): return dict(ok=False, error="Pick a teammate.")
        if not self._uid(): return dict(ok=False, error="Sign in first.")
        try: return self._sync.set_credit(kind, str(id), str(to))
        except lsync.Offline: return dict(ok=False, error="You're offline. Try again when you're connected.")
        except Exception as e: return dict(ok=False, error=str(e)[:140])

    def get_person(self, pid):
        try:
            r = self._sync.person(str(pid))
        except lsync.Offline:
            return dict(ok=False, error="You're offline.")
        except Exception as e:
            return dict(ok=False, error=str(e)[:140])
        return dict(ok=bool(r), person=r)

    def change_password(self, new):
        new = str(new or "")
        me = self._sync.me() or {}
        if len(new) < 8 or not re.search(r"[A-Za-z]", new) or not re.search(r"\d", new):
            return dict(ok=False, error="Use at least 8 characters with a letter and a number.")
        if new.lower() == (me.get("username", "") + "123"):
            return dict(ok=False, error="Pick something different from the starter password.")
        try:
            self._sync.change_password(new)
        except lsync.Offline:
            return dict(ok=False, error="No connection. Try again when you are online.")
        except Exception as e:
            return dict(ok=False, error="Could not change the password: " + str(e)[:120])
        return dict(ok=True, me=self._sync.me())

    def sync_status(self):
        return self._sync.status

    def sync_retry(self):
        self._sync.retry_blocked()
        return dict(ok=True)

    def sync_details(self):
        return self._sync.details()

    def get_people(self):
        return self._sync.people()

    def get_team(self):
        return self._sync.team()

    # ----- Messages: database functions, private files, and the live connection (rules live in the database)
    def sb_rpc(self, fn, args=None):
        return self._sync.msg_rpc(fn, args if args is not None else {})

    def sb_storage(self, op, paths, opts=None):
        return self._sync.msg_storage(op, paths, opts)

    def sb_session(self):
        return self._sync.session_info()

    def sb_group_picture(self, data_url):
        return self._sync.msg_group_picture(data_url)

    def set_event_done(self, id, done):
        try:
            eid = int(id)
        except (TypeError, ValueError):
            return dict(ok=False)
        with self._lock:
            self._db.execute("UPDATE events SET done=?, done_at=? WHERE id=?",
                             (1 if done else 0, datetime.now().strftime("%Y-%m-%d %H:%M") if done else "", eid))
            self._db.commit()
        return dict(ok=True)

    # ----- notes and call scripts (personal = only you; shared = the whole team) -----
    def _uid(self):
        return self._sync.auth.uid()

    def get_notes(self):
        uid = self._uid()
        names = {p["id"]: p["display_name"] for p in self._sync.people()}
        with self._lock:
            rows = self._db.execute("SELECT id,kind,scope,title,folder,body,owner_id,created_at FROM notes "
                                    "WHERE scope='shared' OR owner_id=? OR owner_id='' ORDER BY title COLLATE NOCASE", (uid,)).fetchall()
            upd = {r[0]: r[1] for r in self._db.execute("SELECT local_id,queued_at FROM outbox WHERE tbl='notes'")}
        return [dict(id=r[0], kind=r[1], scope=r[2], title=r[3] or "Untitled", folder=r[4] or "", body=r[5] or "",
                     owner_id=r[6] or uid, owner=names.get(r[6] or uid, "You"), mine=(r[6] or uid) == uid, created=r[7] or "",
                     unsynced=str(r[0]) in upd) for r in rows]

    def save_note(self, d):
        if not isinstance(d, dict):
            return dict(ok=False, error="Nothing to save.")
        kind = "script" if d.get("kind") == "script" else "note"
        scope = "shared" if d.get("scope") == "shared" else "personal"
        title = str(d.get("title") or "").strip()[:120] or "Untitled"
        folder = str(d.get("folder") or "").strip()[:60]
        body = str(d.get("body") or "")
        if len(body) > 600000:
            return dict(ok=False, error="This is too long to save (limit about 600,000 characters).")
        if kind == "script":
            body = sanitize_html(body)
        uid = self._uid()
        try:
            nid = int(d.get("id") or 0)
        except (TypeError, ValueError):
            nid = 0
        with self._lock:
            row = self._db.execute("SELECT owner_id,scope FROM notes WHERE id=?", (nid,)).fetchone() if nid else None
            if row:
                if row[1] == "personal" and row[0] and row[0] != uid:
                    return dict(ok=False, error="That note belongs to someone else.")
                if row[0] and row[0] != uid:
                    scope = row[1]                                   # only the owner may change visibility
                cur = self._db.execute("UPDATE notes SET kind=?,scope=?,title=?,folder=?,body=? WHERE id=? AND (body!=? OR title!=? OR folder!=? OR scope!=? OR kind!=?)",
                                       (kind, scope, title, folder, body, nid, body, title, folder, scope, kind))
            else:
                cur = self._db.execute("INSERT INTO notes(kind,scope,title,folder,body,owner_id,created_at) VALUES(?,?,?,?,?,?,?)",
                                       (kind, scope, title, folder, body, uid, datetime.now().strftime("%Y-%m-%d %H:%M")))
                nid = cur.lastrowid
            self._db.commit()
        self._sync.kick()
        return dict(ok=True, id=nid, body=body)

    def delete_note(self, id):
        try:
            nid = int(id)
        except (TypeError, ValueError):
            return dict(ok=False)
        uid = self._uid()
        me = self._sync.me() or {}
        with self._lock:
            row = self._db.execute("SELECT owner_id,scope FROM notes WHERE id=?", (nid,)).fetchone()
            if not row:
                return dict(ok=True)
            if row[0] and row[0] != uid and not (row[1] == "shared" and me.get("role") == "admin"):
                return dict(ok=False, error="Only the owner can delete this.")
            self._db.execute("DELETE FROM notes WHERE id=?", (nid,))
            self._db.commit()
        self._sync.kick()
        return dict(ok=True)

    # ----- shared call log -----
    def get_calls(self, f=None):
        try:
            return self._sync.calls(f if isinstance(f, dict) else {})
        except lsync.Offline:
            return dict(ok=False, error="You're offline. The call log needs a connection.")
        except lsync.AuthLost:
            return dict(ok=False, error="Signed out.")
        except Exception as e:
            return dict(ok=False, error="Couldn't load the call log: " + str(e)[:140])

    def log_call(self, d):
        d = d if isinstance(d, dict) else {}
        outcome = str(d.get("outcome") or "")
        if outcome not in lsync.Sync.OUTCOMES:
            return dict(ok=False, error="Pick what happened on the call.")
        uid = self._uid()
        if not uid:
            return dict(ok=False, error="Sign in first.")
        lid = str(d.get("lead_id") or "")
        phone = str(d.get("phone") or "").strip()[:40]
        with self._lock:
            row = self._db.execute("SELECT phone FROM leads WHERE id=?", (lid,)).fetchone() if lid else None
        if lid and not row:
            lid = ""
        if row and not phone:
            phone = row[0] or ""
        if not lid and not phone:
            return dict(ok=False, error="Choose the business, or type the phone number.")
        when = lsync.to_iso(str(d.get("when") or "").replace("T", " ")[:16]) or lsync.now_iso()
        rec = dict(lead_id=lid or None, employee_id=uid, phone=phone, started_at=when, outcome=outcome,
                   notes=str(d.get("notes") or "")[:1000], source="app")
        self._sync.queue_call(rec)
        return dict(ok=True)

    # ----- administrators -----
    def _admin(self):
        me = self._sync.me() or {}
        return me.get("role") == "admin"

    def admin_people(self):
        if not self._admin():
            return dict(ok=False, error="Administrators only.")
        try:
            return dict(ok=True, people=self._sync.admin_people(), targets=(self._sync.team() or {}).get("targets", {}))
        except lsync.Offline:
            return dict(ok=False, error="You're offline.")
        except Exception as e:
            return dict(ok=False, error=str(e)[:160])

    def admin_update(self, pid, role=None, active=None):
        if not self._admin():
            return dict(ok=False, error="Administrators only.")
        me = self._sync.me() or {}
        if pid == me.get("id"):
            return dict(ok=False, error="You can't change your own role or deactivate yourself here.")
        try:
            self._sync.admin_update(str(pid), role, active)
            return dict(ok=True)
        except lsync.Offline:
            return dict(ok=False, error="You're offline.")
        except Exception as e:
            return dict(ok=False, error=str(e)[:160])

    def admin_targets(self, t):
        if not self._admin():
            return dict(ok=False, error="Administrators only.")
        try:
            return dict(ok=True, targets=self._sync.admin_targets(t or {}))
        except (TypeError, ValueError):
            return dict(ok=False, error="Targets must be whole numbers.")
        except lsync.Offline:
            return dict(ok=False, error="You're offline.")
        except Exception as e:
            return dict(ok=False, error=str(e)[:160])

    def admin_export(self, path=""):
        if not self._admin():
            return dict(ok=False, error="Administrators only.")
        if not path:
            folder = os.path.join(os.path.expanduser("~"), "Documents")
            path = os.path.join(folder if os.path.isdir(folder) else DATA, "leafline_company_" + datetime.now().strftime("%Y-%m-%d"))
        try:
            return dict(ok=True, files=self._sync.admin_export(path), folder=os.path.dirname(os.path.abspath(path)))
        except lsync.Offline:
            return dict(ok=False, error="You're offline.")
        except Exception as e:
            return dict(ok=False, error="Export failed: " + str(e)[:160])

    def get_prefs(self):
        with self._lock:
            rows = self._db.execute("SELECT k,v FROM sync_kv WHERE k LIKE 'pref:%'").fetchall()
        out = {}
        for k, v in rows:
            try:
                out[k[5:]] = json.loads(v)
            except ValueError:
                pass
        return out

    def set_pref(self, k, v):
        k = re.sub(r"[^A-Za-z0-9_]", "", str(k))[:30]
        val = json.dumps(v)
        if not k or len(val) > 2000:
            return dict(ok=False)
        self._sync._kv("pref:" + k, val)
        return dict(ok=True)

    def get_profile(self):
        return self._profile

    def save_profile(self, d):
        self._profile = clean_profile(d, self._profile)
        try:
            with open(self._profile_path, "w", encoding="utf-8") as fh:
                json.dump(self._profile, fh, indent=2)
        except OSError:
            pass
        return self._profile

    # ----- reading -----
    def get_find(self, scope="all"):
        now = datetime.now()
        if scope == "current":
            rows = self._rows("status='none' AND search=?", (self._current or "",),
                              "ORDER BY CAST(reviews AS INTEGER) DESC, name COLLATE NOCASE")
        else:
            rows = self._rows("status='none'", (), "ORDER BY CAST(reviews AS INTEGER) DESC, name COLLATE NOCASE")
        return [lead_dict(r, now) for r in rows]

    def get_called(self):
        now = datetime.now()
        rows = self._rows("status!='none'", (), "ORDER BY LOWER(btype), called_at DESC, name COLLATE NOCASE")
        try:
            cm = self._sync.callers()
            nm = {p["id"]: p.get("display_name") or p.get("username") or "" for p in self._sync.people()}
        except Exception:
            cm, nm = {}, {}
        out = []
        for r in rows:
            d = lead_dict(r, now)
            u = cm.get(str(d["id"]), "")
            d["called_by"], d["called_by_name"] = u, nm.get(u, "") if u else ""
            out.append(d)
        return out

    def stats(self):
        today = datetime.now().date()
        keys = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        labels = [SHORT[(today - timedelta(days=i)).weekday()] for i in range(6, -1, -1)]
        with self._lock:
            q = self._db.execute
            total = q("SELECT COUNT(*) FROM leads").fetchone()[0]
            uncalled = q("SELECT COUNT(*) FROM leads WHERE status='none'").fetchone()[0]
            counts = dict(q("SELECT status,COUNT(*) FROM leads GROUP BY status").fetchall())
            added = dict(q("SELECT substr(added_at,1,10),COUNT(*) FROM leads WHERE added_at>=? GROUP BY 1", (keys[0],)).fetchall())
            calls = dict(q("SELECT substr(called_at,1,10),COUNT(*) FROM leads WHERE status!='none' AND called_at>=? GROUP BY 1", (keys[0],)).fetchall())
            meets = dict(q("SELECT substr(called_at,1,10),COUNT(*) FROM leads WHERE status='green' AND called_at>=? GROUP BY 1", (keys[0],)).fetchall())
            conv = []
            for k in keys:
                n, g = q("SELECT COUNT(*), SUM(status='green') FROM leads WHERE status!='none' AND substr(called_at,1,10)<=?", (k,)).fetchone()
                conv.append(round(100.0 * (g or 0) / n, 1) if n else 0.0)
            types = q("SELECT MIN(btype),COUNT(*) FROM leads GROUP BY LOWER(btype) ORDER BY 2 DESC, 1 LIMIT 5").fetchall()
        called = total - uncalled
        green = counts.get("green", 0)
        s_added, s_calls, s_meets = ([d.get(k, 0) for k in keys] for d in (added, calls, meets))
        return dict(total=total, uncalled=uncalled, called=called, meetings=green, interested=counts.get("yellow", 0),
                    noanswer=counts.get("orange", 0), rejected=counts.get("red", 0),
                    conversion=round(100.0 * green / called, 1) if called else 0.0,
                    series=dict(added=s_added, calls=s_calls, meets=s_meets, conv=conv), labels=labels,
                    week=dict(added=sum(s_added), calls=sum(s_calls), meets=sum(s_meets), conv=round(conv[-1] - conv[0], 1)),
                    types=[dict(name=t or "Other", count=c) for t, c in types], today_calls=s_calls[-1],
                    goal=self._profile["goal"], money=self._money())

    # ----- profits (deals typed in by hand) -----
    def _deals(self):
        with self._lock:
            rows = self._db.execute(f"SELECT {DEAL_COLS} FROM deals ORDER BY closed_at DESC, id DESC").fetchall()
        return [deal_dict(r) for r in rows]

    def get_deals(self):
        today = datetime.now().date()
        out = []
        for d in self._deals():
            d.update(deal_summary(d, today))
            d["confirmed"] = sorted(d["confirmed"])
            out.append(d)
        return out

    def save_deal(self, d):
        c, err = clean_deal(d)
        if err:
            return dict(ok=False, error=err)
        vals = (c["client"], c["upfront"], c["monthly"], c["months"], c["closed_at"], c["first_bill"], c["notes"])
        try:
            did = int(d.get("id") or 0)
        except (TypeError, ValueError):
            did = 0
        with self._lock:
            if did and self._db.execute("SELECT 1 FROM deals WHERE id=?", (did,)).fetchone():
                self._db.execute("UPDATE deals SET client=?,upfront=?,monthly=?,months=?,closed_at=?,first_bill=?,notes=? WHERE id=?",
                                 vals + (did,))
            else:
                self._db.execute("INSERT INTO deals(client,upfront,monthly,months,closed_at,first_bill,notes,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                 vals + (datetime.now().strftime("%Y-%m-%d %H:%M"),))
            self._db.commit()
        return dict(ok=True)

    def delete_deal(self, id):
        try:
            did = int(id)
        except (TypeError, ValueError):
            return dict(ok=False)
        with self._lock:
            self._db.execute("DELETE FROM deals WHERE id=?", (did,))
            self._db.commit()
        return dict(ok=True)

    def _money(self, today=None):
        """Numbers for the Profits page and the Dashboard hero. A payment counts as received only once someone confirms it
        (its date passing is not enough). Weeks run Monday to Sunday."""
        today = today or datetime.now().date()
        w0 = today - timedelta(days=today.weekday())
        w1 = w0 + timedelta(days=6)
        m0 = today.replace(day=1)
        nd = calendar.monthrange(today.year, today.month)[1]
        m1 = m0.replace(day=nd)
        lo, hi = min(w0, m0), max(w1, m1)
        deals = self._deals()
        daily, dmade, wdays, wpay, todo = [0.0] * nd, [0.0] * nd, [0.0] * 7, [], []
        collected = on_way = mrr = waiting = made = 0.0
        closed_week = 0
        for d in deals:
            sm = deal_summary(d, today)
            collected += sm["collected"]
            waiting += sm["unconfirmed"]
            on_way += sm["remaining"] or 0.0
            if sm["unconfirmed_count"]:
                for dt, amt, kind in deal_payments(d):
                    if dt > today:
                        break
                    if not is_confirmed(d, dt, kind):
                        todo.append(dict(deal_id=d["id"], client=d["client"], date=dt.isoformat(), amount=money(amt), kind=kind))
            if d["monthly"] > 0 and sm["next_date"]:
                mrr += d["monthly"]
            c = parse_day(d["closed_at"])
            if c and w0 <= c <= w1:
                closed_week += 1
            for dt, amt, kind in payments_between(d, lo, hi):
                ok = is_confirmed(d, dt, kind)
                if m0 <= dt <= m1:
                    daily[dt.day - 1] += amt
                    if ok:
                        made += amt; dmade[dt.day - 1] += amt
                if w0 <= dt <= w1:
                    wdays[(dt - w0).days] += amt
                    wpay.append(dict(deal_id=d["id"], client=d["client"], date=dt.isoformat(), amount=money(amt), kind=kind, paid=ok, due=dt <= today))
        wpay.sort(key=lambda p: (p["date"], p["client"].lower()))
        todo.sort(key=lambda p: (p["date"], p["client"].lower()))
        rest = sum(daily) - made
        got = sum(p["amount"] for p in wpay if p["paid"])
        return dict(
            today=today.isoformat(),
            month=dict(label=today.strftime("%B %Y"), made=money(made), rest=money(rest), total=money(made + rest),
                       daily=[money(x) for x in daily], daily_made=[money(x) for x in dmade], today=today.day, days=nd),
            week=dict(start=w0.isoformat(), end=w1.isoformat(), projected=money(sum(wdays)), received=money(got),
                      upcoming=money(sum(wdays) - got), closed=closed_week, payments=wpay,
                      days=[dict(label=SHORT[i], date=(w0 + timedelta(days=i)).isoformat(), amount=money(wdays[i]),
                                 future=w0 + timedelta(days=i) > today) for i in range(7)]),
            all=dict(collected=money(collected), on_the_way=money(on_way), mrr=money(mrr), deals=len(deals),
                     unconfirmed=money(waiting), to_confirm=todo[-200:]))

    def confirm_payment(self, id, day, kind, on=True):
        """Tick (or untick) one payment of a deal as really received. Only payments dated today or earlier."""
        try:
            did = int(id)
        except (TypeError, ValueError):
            return dict(ok=False, error="Deal not found.")
        dt = parse_day(day)
        if not dt or kind not in ("upfront", "monthly"):
            return dict(ok=False, error="That payment doesn't exist.")
        if on and dt > datetime.now().date():
            return dict(ok=False, error="This payment isn't due yet. You can confirm it on or after its date.")
        with self._lock:
            row = self._db.execute(f"SELECT {DEAL_COLS} FROM deals WHERE id=?", (did,)).fetchone()
            if not row:
                return dict(ok=False, error="Deal not found.")
            d = deal_dict(row)
            if not any(p[0] == dt and p[2] == kind for p in payments_between(d, dt, dt)):
                return dict(ok=False, error="That payment doesn't exist.")
            keys = set(d["confirmed"])
            (keys.add if on else keys.discard)(pay_key(dt, kind))
            self._db.execute("UPDATE deals SET confirmed=? WHERE id=?", (",".join(sorted(keys)), did))
            self._db.commit()
        return dict(ok=True, confirmed=bool(on))

    # ----- calendar -----
    def get_calendar(self, lo, hi):
        """Everything dated between lo and hi (ISO dates): meetings, deal payments, closed deals and your own events."""
        lo, hi = parse_day(lo), parse_day(hi)
        if not lo or not hi or hi < lo or (hi - lo).days > 400:
            return []
        today = datetime.now().date()
        los, his = lo.isoformat(), hi.isoformat()
        with self._lock:
            meet = self._db.execute("SELECT id,name,phone,owner,meeting_at FROM leads WHERE status='green' AND meeting_at!='' "
                                    "AND substr(meeting_at,1,10) BETWEEN ? AND ?", (los, his)).fetchall()
            evs = [event_dict(r) for r in self._db.execute(f"SELECT {EVENT_COLS} FROM events").fetchall()]
            linked = {}
            for lid in {e["lead_id"] for e in evs if e["lead_id"]}:
                row = self._db.execute("SELECT name,phone FROM leads WHERE id=?", (lid,)).fetchone()
                if row:
                    linked[lid] = row
        items = []
        for lid, name, phone, owner, at in meet:
            items.append(dict(src="meeting", key=f"m:{lid}", title=name or "", date=at[:10], time=at[11:16], lead_id=lid,
                              phone=phone or "", owner=owner if owner and owner != NA else ""))
        for d in self._deals():
            c = parse_day(d["closed_at"])
            if c and lo <= c <= hi:
                items.append(dict(src="closed", key=f"c:{d['id']}", title=d["client"], date=c.isoformat(), time="", deal_id=d["id"]))
            for dt, amt, kind in payments_between(d, lo, hi):
                items.append(dict(src="payment", key=f"p:{d['id']}:{dt.isoformat()}:{kind}", title=d["client"], date=dt.isoformat(), time="",
                                  amount=money(amt), kind=kind, paid=is_confirmed(d, dt, kind), due=dt <= today, deal_id=d["id"]))
        names = {p["id"]: p["display_name"] for p in self._sync.people()}
        for e in evs:
            for dt in event_dates(e, lo, hi):
                nm = linked.get(e["lead_id"])
                items.append(dict(src="event", key=f"e:{e['id']}:{dt.isoformat()}", id=e["id"], title=e["title"], date=dt.isoformat(),
                                  start=e["date"], time=e["time"], color=e["color"], icon=e["icon"], repeat=e["repeat"], until=e["until"],
                                  notes=e["notes"], lead_id=e["lead_id"], lead_name=nm[0] if nm else "", phone=nm[1] if nm else "",
                                  assigned_to=e["assigned_to"], assigned_name=names.get(e["assigned_to"], ""), created_name=names.get(e["created_by"], ""),
                                  done=e["done"]))
        order = {"meeting": 0, "event": 1, "payment": 2, "closed": 3}
        items.sort(key=lambda i: (i["date"], i.get("time") or "", order[i["src"]], i["title"].lower()))
        return items

    def save_event(self, d):
        c, err = clean_event(d)
        if err:
            return dict(ok=False, error=err)
        who = str(d.get("assigned_to") or "")
        if who and who not in {p["id"] for p in self._sync.people()}:
            who = ""
        vals = (c["title"], c["day"], c["start_time"], c["color"], c["icon"], c["repeat"], c["until"], c["notes"], c["lead_id"], who)
        try:
            eid = int(d.get("id") or 0)
        except (TypeError, ValueError):
            eid = 0
        with self._lock:
            if eid and self._db.execute("SELECT 1 FROM events WHERE id=?", (eid,)).fetchone():
                self._db.execute("UPDATE events SET title=?,day=?,start_time=?,color=?,icon=?,repeat_kind=?,until=?,notes=?,lead_id=?,assigned_to=? WHERE id=?",
                                 vals + (eid,))
            else:
                self._db.execute("INSERT INTO events(title,day,start_time,color,icon,repeat_kind,until,notes,lead_id,assigned_to,created_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                 vals + (datetime.now().strftime("%Y-%m-%d %H:%M"), self._sync.auth.uid()))
            self._db.commit()
        return dict(ok=True)

    def delete_event(self, id):
        try:
            eid = int(id)
        except (TypeError, ValueError):
            return dict(ok=False)
        with self._lock:
            self._db.execute("DELETE FROM events WHERE id=?", (eid,))
            self._db.commit()
        return dict(ok=True)

    def set_meeting(self, id, when):
        """when = 'YYYY-MM-DD HH:MM' (or with a T); empty clears the meeting time."""
        w = str(when or "").strip().replace("T", " ")
        if w:
            try:
                w = datetime.strptime(w[:16], "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return dict(ok=False, error="Pick a valid date and time.")
        with self._lock:
            cur = self._db.execute("UPDATE leads SET meeting_at=? WHERE id=?", (w, str(id)))
            self._db.commit()
        return dict(ok=cur.rowcount > 0)

    # ----- editing -----
    def mark(self, ids, status):
        if status not in STATUS_LABELS or not isinstance(ids, list):
            return dict(ok=False)
        when = None if status == "none" else datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._lock:
            for i in ids:
                self._db.execute("UPDATE leads SET status=?, called_at=? WHERE id=?", (status, when, str(i)))
            self._db.commit()
        try: self._sync.note_callers(ids, status)
        except Exception: pass
        return dict(ok=True, n=len(ids))

    def save_lead(self, id, owner, notes):
        with self._lock:
            self._db.execute("UPDATE leads SET owner=?, notes=? WHERE id=?",
                             ((owner or "").strip()[:80] or NA, (notes or "").strip()[:2000], str(id)))
            self._db.commit()
        return dict(ok=True, owner=(owner or "").strip()[:80] or NA)

    def open_site(self, id):
        rows = self._rows("id=?", (str(id),))
        w = rows[0][8] if rows else NA
        if not w or w == NA:
            return dict(ok=False)
        webbrowser.open(w if w.lower().startswith("http") else "http://" + w)
        return dict(ok=True)

    def export_csv(self, called, scope="all", path=""):
        """path comes from the Save dialog in the Electron window; without one the file goes to Documents."""
        name = "leafline_called_leads.csv" if called else "leafline_leads.csv"
        if not path:
            folder = os.path.join(os.path.expanduser("~"), "Documents")
            path = os.path.join(folder if os.path.isdir(folder) else DATA, name)
        if not str(path).lower().endswith(".csv"):
            path = str(path) + ".csv"
        leads = self.get_called() if called else self.get_find(scope)
        with self._lock:
            extra = {r[0]: r[1] for r in self._db.execute("SELECT id,website FROM leads")}
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                head = ["Business type", "Company", "Phone", "Owner", "Open now", "Hours today", "Rating", "Reviews", "Website", "Address", "Notes"]
                w.writerow((["Result"] if called else []) + (head[:4] + ["Last called"] + head[4:] if called else head))
                for l in leads:
                    row = [l["btype"], l["name"], l["phone"], l["owner"]]
                    if called:
                        row.append(l["called_at"])
                    row += [{"open": "Open", "closed": "Closed"}.get(l["open"], NA), l["hours"], l["rating"], l["reviews"],
                            extra.get(l["id"], NA), l["address"], l["notes"]]
                    w.writerow(([STATUS_LABELS[l["status"]]] if called else []) + row)
        except OSError as e:
            return dict(ok=False, error=str(e))
        return dict(ok=True, path=str(path), n=len(leads))

    # ----- searching -----
    def search(self, country, state, city, btype):
        if self._busy:
            return dict(ok=False, error="A search is already running.")
        t = " ".join((btype or "").split())
        area = ", ".join(x.strip() for x in (city, state, country) if x and x.strip())
        if not t or not area:
            return dict(ok=False, error="Enter a business type and at least a country, state/province or city.")
        self._bt = norm_type(t)
        self._q = self._current = f"{self._bt} | {area}"
        self._n = self._skipped = 0
        self._stop.clear()
        self._busy = True
        threading.Thread(target=self._work, args=(f"{t} in {area}",), daemon=True).start()
        return dict(ok=True, q=self._q)

    def stop(self):
        self._stop.set()
        return dict(ok=True)

    def _work(self, q):
        result, err = None, None
        try:
            for p in gmaps_scrape(q, self._profile["max_results"], self._say, self._stop):
                self._add_one(p)
            with self._lock:
                self._db.commit()
            if self._n and not self._stop.is_set():
                self._enrich_all()
            with self._lock:
                own = self._db.execute("SELECT COUNT(*) FROM leads WHERE status='none' AND search=? AND owner!='N/A'", (self._q,)).fetchone()[0]
            result = dict(n=self._n, skipped=self._skipped, owners=own, stopped=self._stop.is_set(), q=self._q)
        except Exception as e:
            err = str(e)
        self._busy = False
        if err is not None:
            self._emit("search_error", dict(error=err))
        else:
            self._emit("search_done", result)

    def _add_one(self, p):
        d = re.sub(r"\D", "", p["phone"])[-10:]
        with self._lock:
            row = self._db.execute("SELECT status FROM leads WHERE id=?", (p["id"],)).fetchone()
            if (row and row[0] != "none") or self._db.execute(
                    "SELECT 1 FROM leads WHERE status!='none' AND pdigits=? AND id!=?", (d, p["id"])).fetchone():
                self._skipped += 1  # already called: stays on the Called page, never re-listed
                return
            self._db.execute(
                """INSERT INTO leads(id,name,phone,pdigits,address,website,rating,reviews,search,btype,hours,added_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET search=excluded.search, btype=excluded.btype, rating=excluded.rating,
                     reviews=excluded.reviews, hours=CASE WHEN excluded.hours!='' THEN excluded.hours ELSE leads.hours END""",
                (p["id"], p["name"], p["phone"], d, p["address"], p["website"], p["rating"], p["reviews"], self._q, self._bt,
                 p.get("hours", ""), datetime.now().strftime("%Y-%m-%d %H:%M")))
            self._db.commit()
            self._n += 1
            rows = self._db.execute(f"SELECT {LEAD_COLS} FROM leads WHERE id=?", (p["id"],)).fetchall()
        if rows:
            self._emit("lead", lead_dict(rows[0]))

    def _enrich_all(self):
        with self._lock:
            todo = self._db.execute("SELECT id,website FROM leads WHERE status='none' AND search=? AND enriched=0 AND website!=?",
                                    (self._q, NA)).fetchall()
        if not todo:
            self._say(f"Done: {self._n} businesses to call.", 1.0)
            return

        def one(r):
            try:
                return r[0], enrich(r[1])
            except Exception:
                return r[0], (NA, NA, NA)
        with ThreadPoolExecutor(8) as ex:
            futs, n = [ex.submit(one, r) for r in todo], 0
            for f in as_completed(futs):
                if self._stop.is_set():
                    for x in futs:
                        x.cancel()
                    break
                n += 1
                id_, (o, rt, rv) = f.result()
                with self._lock:
                    self._db.execute("""UPDATE leads SET enriched=1,
                        owner=CASE WHEN owner='N/A' THEN ? ELSE owner END, rating=CASE WHEN rating='N/A' THEN ? ELSE rating END,
                        reviews=CASE WHEN reviews='N/A' THEN ? ELSE reviews END WHERE id=?""", (o, rt, rv, id_))
                    if n % 10 == 0:
                        self._db.commit()
                self._say(f"Got {self._n} businesses. Checked {n}/{len(todo)} websites for owner names...", 0.9 + 0.1 * n / len(todo))
                if n % 10 == 0:
                    self._emit("refresh")
        with self._lock:
            self._db.commit()





UI_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Leafline Web Services - Lead Finder</title>
<script>try{var lfT=localStorage.getItem("lf_theme");if(lfT==="emerald"||lfT==="midnight")document.documentElement.dataset.theme=lfT}catch(e){}</script>
<style>
@font-face{font-family:"InterLocal";src:local("Inter"),url("__FONT_REG__") format("truetype");font-weight:400}
@font-face{font-family:"InterLocal";src:local("Inter Bold"),local("Inter SemiBold"),url("__FONT_BOLD__") format("truetype");font-weight:600 800}
:root{
  /* ====== DESIGN TOKENS (Leafline 11). Themes below only swap these. ====== */
  --bg:#0A120E; --bg-glow:rgba(74,222,139,.13); --panel:#111D16; --card:#15241B; --card-end:#122019; --card2:#1B2D22; --card3:#22392B;
  --main1:#132219; --main2:#0F1B14; --side1:#17301F; --side2:#10231A; --av-bg:#183626;
  --line:rgba(170,230,195,.10); --line2:rgba(170,230,195,.18);
  --text:#ECF5EF; --text2:#CFE2D6; --muted:#97B0A1; --faint:#6E8A7A;
  --accent:#4ADE8B; --accent2:#2FBF71; --accent-hi:#9AF2C2; --accent-text:#04210F; --accent-soft:rgba(74,222,139,.13); --accent-line:rgba(74,222,139,.38);
  --glow:rgba(74,222,139,.32); --glow-soft:rgba(74,222,139,.16);
  --ok:#5BE39A; --warn:#EBC15C; --orange:#EE9A5A; --bad:#F08A8A; --info:#8FC7F0;
  --g:#3FD487; --gt:#04210F; --y:#E9C15A; --yt:#211A05; --o:#EB955A; --ot:#26130A; --r:#E46F6F; --rt:#2A0909;
  /* motion */
  --e-out:cubic-bezier(.22,1,.36,1); --e-spring:cubic-bezier(.34,1.32,.64,1); --e-bounce:cubic-bezier(.3,1.5,.6,1); --e-io:cubic-bezier(.65,0,.35,1); --e-in:cubic-bezier(.55,0,.75,.2);
  --spring:var(--e-spring); --smooth:var(--e-out);
  --d-micro:160ms; --d-hover:220ms; --d-pop:280ms; --d-card:380ms; --d-page:480ms; --d-major:760ms;
  /* depth + light */
  --sh:0 14px 32px rgba(0,0,0,.32),0 2px 6px rgba(0,0,0,.22); --sh-lg:0 30px 70px rgba(0,0,0,.5); --hi:inset 0 1px 0 rgba(255,255,255,.06);
  --ring-glow:0 0 0 1px var(--accent-line),0 0 22px var(--glow-soft);
  --glass:rgba(22,38,29,.58); --glass-hi:rgba(255,255,255,.08); --blur:blur(18px) saturate(150%);
  --r-sm:12px; --r-md:18px; --r-lg:24px; --r-xl:30px;
  --z-nav:30; --z-pop:60; --z-modal:70; --z-login:90; --z-toast:100; --z-intro:120;
  --font:"InterLocal","Inter","Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;
  color-scheme:dark;
}
:root[data-theme=emerald]{
  --bg:#08130F; --bg-glow:rgba(56,224,170,.14); --panel:#0E1D18; --card:#12261F; --card-end:#0F211B; --card2:#183229; --card3:#1F3D33;
  --main1:#10241D; --main2:#0C1C16; --side1:#123327; --side2:#0C241C; --av-bg:#123A2E;
  --line:rgba(150,240,210,.10); --line2:rgba(150,240,210,.18); --text2:#CBE6DC; --muted:#92B3A7;
  --accent:#3EE0AE; --accent2:#22BF8E; --accent-hi:#97F3D6; --accent-text:#032219; --accent-soft:rgba(62,224,174,.13); --accent-line:rgba(62,224,174,.4);
  --glow:rgba(62,224,174,.34); --glow-soft:rgba(62,224,174,.16); --g:#3ED6A2;
}
:root[data-theme=midnight]{
  --bg:#060908; --bg-glow:rgba(74,222,139,.08); --panel:#0C110E; --card:#101713; --card-end:#0D1310; --card2:#151E19; --card3:#1B2720;
  --main1:#0D1310; --main2:#090E0B; --side1:#111A15; --side2:#0B110D; --av-bg:#14261C;
  --line:rgba(190,230,205,.08); --line2:rgba(190,230,205,.15); --text2:#C9D8CF; --muted:#8CA195;
  --accent:#5CD993; --accent2:#3BB774; --accent-hi:#A6EEC5; --accent-soft:rgba(92,217,147,.11); --accent-line:rgba(92,217,147,.32);
  --glow:rgba(92,217,147,.26); --glow-soft:rgba(92,217,147,.12); --glass:rgba(14,21,17,.6);
}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{font-family:var(--font);font-size:14px;line-height:1.4;color:var(--text);background:var(--bg);overflow:hidden;
  background-image:radial-gradient(700px 500px at 8% 4%,var(--bg-glow),transparent 70%),radial-gradient(800px 600px at 96% 100%,var(--bg-glow),transparent 70%);
  -webkit-font-smoothing:antialiased}
button,input,select,textarea{font:inherit;color:inherit}
button{cursor:pointer;border:0;background:none}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.ic{display:inline-flex;width:20px;height:20px;flex:none}.ic svg{width:100%;height:100%;stroke:currentColor;fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.pop:not(.in){opacity:0}

.app{display:grid;grid-template-columns:236px 1fr;gap:18px;padding:18px;height:100vh}
/* sidebar */
.side{position:relative;border-radius:34px;padding:22px 14px 18px;display:flex;flex-direction:column;align-items:center;
  background:linear-gradient(170deg,var(--side1),var(--side2));box-shadow:var(--sh),var(--hi);min-height:0;overflow:hidden}
.side:before{content:"";position:absolute;inset:0;background:radial-gradient(260px 200px at 20% 0,rgba(255,255,255,.16),transparent 70%);pointer-events:none}
.ring{position:relative;width:96px;height:96px;border-radius:50%;padding:4px;background:conic-gradient(from 200deg,var(--accent),#9CF2C3,var(--accent));box-shadow:0 8px 20px rgba(0,0,0,.3);cursor:pointer;transition:transform .5s var(--spring)}
.ring:hover{transform:scale(1.06) rotate(-2deg)}.ring:active{transform:scale(.95)}
.ring .in-av{width:100%;height:100%;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:30px;letter-spacing:.5px;background:var(--av-bg);color:#fff;transition:background .4s}
.ring .dot{position:absolute;right:4px;bottom:6px;width:20px;height:20px;border-radius:50%;background:var(--accent);border:3px solid var(--side2)}
.hi{margin:12px 0 18px;font-weight:700;font-size:16px;text-align:center;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nav{position:relative;width:100%;display:flex;flex-direction:column;gap:6px}
.pill-bg{position:absolute;left:0;right:0;border-radius:16px;background:#EAF7EF;box-shadow:0 8px 18px rgba(0,0,0,.25);transition:top .55s var(--spring),height .3s;z-index:0}
.nv{position:relative;z-index:1;display:flex;align-items:center;gap:12px;height:46px;padding:0 16px;border-radius:16px;color:#D9EEE1;font-weight:600;font-size:14.5px;text-align:left;transition:color .3s,transform .4s var(--spring)}
.nv:hover{transform:translateX(4px);color:#fff}.nv:active{transform:scale(.96)}
.nv.on{color:#0C3320}.nv.on:hover{transform:none}
.nv .badge{margin-left:auto;min-width:22px;height:22px;border-radius:11px;padding:0 6px;display:grid;place-items:center;font-size:12px;font-weight:700;background:rgba(255,255,255,.22);color:#fff;transition:background .3s,color .3s}
.nv.on .badge{background:#0C3320;color:#EAF7EF}
.side .foot{margin-top:auto;font-size:12px;color:var(--text2);text-align:center;padding:10px 6px 0;line-height:1.35}
/* main */
.main{position:relative;border-radius:34px;display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;
  background:linear-gradient(180deg,var(--main1),var(--main2));box-shadow:var(--sh),var(--hi)}
.top{display:flex;align-items:center;gap:16px;padding:22px 28px 6px}
.top h1{font-size:26px;font-weight:800;letter-spacing:-.4px;min-width:170px}
.srch{flex:1;max-width:520px;margin:0 auto;position:relative}
.srch input{width:100%;height:46px;border-radius:23px;border:1px solid var(--line);background:var(--card);padding:0 52px 0 46px;box-shadow:inset 0 2px 6px rgba(0,0,0,.28);transition:border-color .3s,box-shadow .4s,transform .45s var(--spring)}
.srch input::placeholder{color:var(--muted)}
.srch input:focus{outline:0;border-color:var(--accent);box-shadow:0 0 0 4px rgba(74,222,139,.18),inset 0 2px 6px rgba(0,0,0,.28);transform:scale(1.015)}
.srch .ic{position:absolute;left:15px;top:13px;color:var(--muted)}
.srch kbd{position:absolute;right:12px;top:11px;width:24px;height:24px;border-radius:50%;background:var(--card2);color:var(--muted);display:grid;place-items:center;font-size:12px;font-weight:700;font-family:var(--font)}
.rb{position:relative;width:46px;height:46px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(160deg,#4BE08F,#2BB567);color:var(--accent-text);box-shadow:0 8px 16px rgba(0,0,0,.3),var(--hi);transition:transform .45s var(--spring),box-shadow .3s}
.rb:hover{transform:translateY(-3px) scale(1.08)}.rb:active{transform:scale(.92)}
.rb .cnt{position:absolute;top:-4px;right:-4px;min-width:20px;height:20px;border-radius:10px;padding:0 5px;background:var(--bad);color:#2b0507;font-size:11.5px;font-weight:800;display:grid;place-items:center;transform:scale(0);transition:transform .5s var(--spring)}
.rb .cnt.on{transform:scale(1)}
.pages{position:relative;flex:1;min-height:0}
.page{display:none;position:absolute;inset:0;overflow:auto;padding:14px 28px 96px}
.page.on{display:block}
.page.flex.on{display:flex;flex-direction:column}
.page::-webkit-scrollbar,.scr::-webkit-scrollbar{width:10px;height:10px}
.page::-webkit-scrollbar-thumb,.scr::-webkit-scrollbar-thumb{background:var(--line);border-radius:6px;border:2px solid transparent;background-clip:content-box}
/* generic */
.card{background:linear-gradient(180deg,var(--card),var(--card-end));border-radius:26px;box-shadow:var(--sh),var(--hi);border:1px solid rgba(255,255,255,.03)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:40px;padding:0 18px;border-radius:20px;background:var(--card2);color:var(--text);font-weight:600;font-size:13.5px;box-shadow:var(--hi),0 4px 10px rgba(0,0,0,.2);transition:transform .45s var(--spring),background .25s,box-shadow .3s,filter .25s}
.btn:hover{transform:translateY(-2px);background:var(--card3);box-shadow:var(--hi),0 8px 16px rgba(0,0,0,.3)}.btn:active{transform:scale(.94)}
.btn.pri{background:linear-gradient(160deg,#4BE08F,#2BB567);color:var(--accent-text);height:44px;padding:0 24px;font-size:14.5px;font-weight:700}
.btn.pri:hover{background:linear-gradient(160deg,#5BEB9C,#33C873)}
.btn.stop{background:linear-gradient(160deg,#FF7C80,#E5484D);color:#2b0507}
.btn[disabled]{opacity:.55;pointer-events:none}
.btn.sm{height:34px;padding:0 14px;font-size:13px}
.pill{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border-radius:12px;font-size:12.5px;font-weight:700;white-space:nowrap}
.pill:before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.pill.open{background:rgba(52,210,123,.18);color:#7DF0A8}
.pill.closed{background:rgba(255,107,112,.18);color:#FF9AA0}
.pill.unknown{background:rgba(163,187,172,.16);color:var(--text2)}
.muted{color:var(--muted)}
select,.inp{height:40px;border-radius:14px;border:1px solid var(--line);background:var(--panel);padding:0 14px;transition:border-color .3s,box-shadow .35s,transform .4s var(--spring)}
select{appearance:none;padding-right:34px;cursor:pointer;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' fill='none' stroke='%23A3BBAC' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M1 1.5l5 5 5-5'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 13px center}
select:hover,.inp:hover{border-color:var(--line2)}
select:focus,.inp:focus{outline:0;border-color:var(--accent);box-shadow:0 0 0 4px rgba(74,222,139,.16)}
textarea.inp{height:auto;padding:12px 14px;resize:none;line-height:1.45}
label.l{display:block;font-size:12.5px;font-weight:600;color:var(--muted);margin:0 0 6px 4px}
.chip{height:34px;padding:0 14px;border-radius:17px;background:var(--panel);border:1px solid var(--line);font-size:13px;font-weight:600;color:var(--muted);display:inline-flex;align-items:center;gap:7px;transition:all .35s var(--spring)}
.chip:hover{transform:translateY(-2px);color:var(--text)}.chip:active{transform:scale(.94)}
.chip.on{background:rgba(74,222,139,.16);border-color:var(--accent);color:#9CF2C3}
.empty{display:grid;place-items:center;text-align:center;color:var(--muted);padding:34px 24px;gap:10px}
.empty b{color:var(--text);font-size:15px}
.empty .bub{width:64px;height:64px;border-radius:50%;background:var(--card2);display:grid;place-items:center;color:var(--accent);animation:float 3.2s ease-in-out infinite}
@keyframes float{50%{transform:translateY(-6px)}}
/* dashboard */
.banner{position:relative;display:grid;grid-template-columns:260px 1fr 290px;align-items:center;gap:20px;padding:22px 34px;border-radius:30px;overflow:hidden;
  background:linear-gradient(120deg,var(--side1),var(--main2) 75%);box-shadow:var(--sh),var(--hi)}
.banner:before{content:"";position:absolute;right:-60px;top:-80px;width:300px;height:300px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.14),transparent 70%)}
.banner h2{font-size:25px;font-weight:800;letter-spacing:-.3px}
.banner p{margin:8px 0 14px;font-size:15px;color:var(--text2);max-width:430px}
.goal{display:flex;align-items:center;gap:12px;margin-bottom:16px;max-width:430px;font-size:13px;font-weight:600;color:var(--text2)}
.goal .tr{flex:1;height:10px;border-radius:5px;background:rgba(0,0,0,.28);overflow:hidden}
.goal .fl{height:100%;width:0;border-radius:5px;background:linear-gradient(90deg,#7DF0A8,#3DDC84);transition:width 1.1s var(--spring) .3s}
.ill{width:100%;height:150px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:18px 0}
.stat{position:relative;border-radius:26px;padding:16px 18px;box-shadow:var(--sh),var(--hi);transition:transform .5s var(--spring)}
.stat:hover{transform:translateY(-4px) scale(1.02)}
.stat .ico{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;color:#fff;box-shadow:0 6px 12px rgba(0,0,0,.25)}
.stat .lb{font-size:13px;font-weight:600;margin-top:12px;color:var(--text2)}
.stat .vl{font-size:30px;font-weight:800;letter-spacing:-.5px;margin-top:2px}
.stat .dl{font-size:12.5px;font-weight:600;margin-top:2px;color:var(--text2)}
.stat .spark{position:absolute;right:14px;top:18px;width:96px;height:38px;overflow:visible}
.spark path{fill:none;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset 1.2s var(--smooth) .25s}
.in .spark path,.spark.in path{stroke-dashoffset:0}
.s1{background:linear-gradient(160deg,#235139,#1A3A29)}.s2{background:linear-gradient(160deg,#4A431A,#352F12)}.s3{background:linear-gradient(160deg,#1F5A3A,#17402B)}.s4{background:linear-gradient(160deg,#4B2E16,#35210F)}
.two{display:grid;grid-template-columns:1.55fr 1fr;gap:16px}
.card h3{font-size:16px;font-weight:700}
.chart-c{padding:18px 20px}.chart-c .hd,.types .hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.legend{display:flex;gap:16px;font-size:12.5px;color:var(--muted);font-weight:600}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
svg text{font-family:var(--font)}
.bar{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);transition:transform .9s var(--spring);transition-delay:calc(var(--i)*70ms + 250ms)}
.in .bar{transform:scaleY(1)}
.mline{stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset 1.4s var(--smooth) .5s}
.in .mline{stroke-dashoffset:0}
.mdot{transform-box:fill-box;transform-origin:center;transform:scale(0);transition:transform .6s var(--spring);transition-delay:calc(var(--i)*70ms + 900ms)}
.in .mdot{transform:scale(1)}
.types{padding:18px 20px}
.trow{margin:14px 0}.trow .tt{display:flex;justify-content:space-between;font-size:13.5px;font-weight:600;margin-bottom:6px}
.trow .tt span:last-child{color:var(--muted);font-weight:600}
.trow .bt{height:10px;border-radius:5px;background:rgba(0,0,0,.3);overflow:hidden}
.trow .bf{height:100%;width:0;border-radius:5px;transition:width 1s var(--spring) .35s}
/* find */
.fcard{padding:16px 18px 14px;margin-bottom:14px}
.frow{display:grid;grid-template-columns:1fr 1fr 1fr 1.9fr auto;gap:12px;align-items:end}
.frow .inp{width:100%}
.sline{display:flex;align-items:center;gap:12px;margin-top:12px;min-height:22px;font-size:13px;color:var(--muted)}
.sline #sText{flex:1;transition:opacity .3s}
.pbar{height:7px;border-radius:4px;background:rgba(0,0,0,.32);overflow:hidden;margin-top:8px}
.pbar i{display:block;height:100%;width:0;border-radius:4px;background:linear-gradient(90deg,#3DDC84,#9CF2C3);transition:width .7s var(--smooth)}
.pbar.run i{background-size:200% 100%;background-image:linear-gradient(90deg,#2BB567,#9CF2C3,#2BB567);animation:slide 1.6s linear infinite}
@keyframes slide{to{background-position:-200% 0}}
.split{flex:1;min-height:340px;display:grid;grid-template-columns:minmax(430px,1fr) 1.25fr;gap:16px}
.pane{display:flex;flex-direction:column;min-height:0;overflow:hidden;border-radius:28px}
.ph{padding:16px 18px 10px}
.ph h3{font-size:18px;font-weight:800}
.ph .sub{font-size:12.5px;color:var(--muted);margin-top:2px}
.tools{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center}
.tools select{height:34px;font-size:13px;border-radius:17px}
.all{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--muted);margin-left:auto;cursor:pointer}
.list{flex:1;overflow:auto;padding:4px 10px 12px}
.li{position:relative;display:flex;gap:11px;align-items:center;padding:11px 12px;border-radius:20px;cursor:pointer;margin-bottom:4px;border:1px solid transparent;transition:background .3s,transform .45s var(--spring),border-color .3s,box-shadow .3s}
.li:hover{background:rgba(255,255,255,.045);transform:translateX(3px)}
.li.act{background:linear-gradient(160deg,var(--card3),var(--card2));border-color:rgba(74,222,139,.35);box-shadow:0 8px 18px rgba(0,0,0,.28),var(--hi)}
.li.act:hover{transform:none}
.chk{width:22px;height:22px;flex:none;border-radius:50%;border:2px solid var(--faint);display:grid;place-items:center;color:transparent;transition:all .4s var(--spring)}
.chk:hover{border-color:var(--accent);transform:scale(1.15)}
.chk svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}
.li.sel .chk{background:var(--accent);border-color:var(--accent);color:var(--accent-text);transform:scale(1.08)}
.av{width:42px;height:42px;flex:none;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:14px;color:#06210F;box-shadow:0 5px 10px rgba(0,0,0,.25),inset 0 -3px 6px rgba(0,0,0,.12)}
.lm{min-width:0;flex:1}
.lt{display:flex;align-items:center;gap:8px;justify-content:space-between}
.lt b{font-size:14.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ls{display:flex;flex-wrap:wrap;gap:3px 12px;align-items:center;margin-top:5px;font-size:13px;color:var(--muted);min-width:0}
.ls>span{white-space:nowrap}
.ls .rv{font-weight:700;color:#FFD60A}
.ls .rv.none{color:var(--muted);font-weight:500}
.ls .hr{color:var(--text2);font-weight:500}
.li .pill{flex:none}
.dpane{padding:22px 24px 30px;overflow:auto}
.dh{display:flex;align-items:center;gap:14px}
.dh .av{width:54px;height:54px;font-size:18px}
.dh h2{font-size:21px;font-weight:800;letter-spacing:-.3px}
.dh .sub{font-size:13px;color:var(--muted);margin-top:2px}
.dh .acts{margin-left:auto;display:flex;gap:8px;flex:none}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0 14px}
.fact{background:rgba(0,0,0,.2);border-radius:20px;padding:12px 16px;min-height:66px;transition:transform .45s var(--spring),background .3s}
.fact:hover{transform:translateY(-2px);background:rgba(0,0,0,.27)}
.fact .k{font-size:12px;font-weight:700;color:var(--muted);letter-spacing:.3px;text-transform:uppercase}
.fact .v{font-size:15px;font-weight:600;margin-top:5px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;word-break:break-word}
.fact.span{grid-column:1/-1}
.fact .inp{height:34px;width:100%;margin-top:4px;background:var(--bg)}
.mark{margin-top:18px;padding:16px 18px;border-radius:24px;background:rgba(0,0,0,.2)}
.mark .t{font-size:13.5px;font-weight:700;margin-bottom:10px}
.sb{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.st{height:46px;border-radius:16px;font-weight:700;font-size:13px;line-height:1.15;padding:0 8px;box-shadow:0 6px 12px rgba(0,0,0,.28),var(--hi);transition:transform .45s var(--spring),filter .25s}
.st:hover{transform:translateY(-3px) scale(1.03);filter:brightness(1.08)}.st:active{transform:scale(.93)}
.st.g{background:var(--g);color:var(--gt)}.st.y{background:var(--y);color:var(--yt)}.st.o{background:var(--o);color:var(--ot)}.st.r{background:var(--r);color:var(--rt)}
.st.cur{outline:3px solid #fff;outline-offset:2px}
.dsw{animation:dsw .5s var(--smooth)}@keyframes dsw{from{opacity:0;transform:translateX(18px)}}
/* board */
.cstats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:6px 0 14px}
.cstat{border-radius:24px;padding:14px 16px;display:flex;align-items:center;gap:12px;box-shadow:var(--sh),var(--hi);transition:transform .5s var(--spring)}
.cstat:hover{transform:translateY(-3px)}
.cstat .ico{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;flex:none}
.cstat .n{font-size:24px;font-weight:800;line-height:1.1}.cstat .t{font-size:12.5px;font-weight:600;color:var(--text2)}
.board{display:grid;grid-template-columns:repeat(4,minmax(205px,1fr));gap:14px;align-items:start}
.col{border-radius:26px;padding:12px 10px 10px;background:rgba(0,0,0,.2);min-height:260px;transition:background .3s,transform .45s var(--spring),box-shadow .3s}
.col.over{background:rgba(74,222,139,.13);transform:scale(1.02);box-shadow:0 0 0 2px var(--accent)}
.ch{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:4px 8px 10px;font-weight:700;font-size:14px}
.ch i{width:11px;height:11px;border-radius:50%}.ch .n{margin-left:auto;min-width:26px;height:24px;padding:0 8px;border-radius:12px;background:var(--card2);display:grid;place-items:center;font-size:12.5px}
.grp{font-size:12px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:var(--text2);padding:8px 8px 6px;display:flex;justify-content:space-between}
/* Called Leads: each group folds away (and stays folded) with a click on its header */
button.grp{width:100%;align-items:center;gap:8px;text-align:left;border-radius:12px;min-height:34px;margin-top:2px;transition:background-color var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out)}
button.grp:hover{background:rgba(255,255,255,.05);color:var(--text)}
button.grp .gl{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
button.grp .gn{min-width:24px;height:22px;padding:0 7px;border-radius:11px;background:rgba(255,255,255,.07);display:grid;place-items:center;font-size:11.5px;letter-spacing:0}
button.grp .gc{width:16px;height:16px;flex:none;transition:transform var(--d-card) var(--e-spring)}
button.grp[aria-expanded="false"] .gc{transform:rotate(-90deg)}
button.grp[aria-expanded="false"]{color:var(--muted)}button.grp[aria-expanded="false"] .gn{background:var(--cc,rgba(255,255,255,.12));color:#0C1A12}
.gb{display:grid;grid-template-rows:1fr;transition:grid-template-rows var(--d-card) var(--e-out),opacity var(--d-card) var(--e-out)}
.gb>div{min-height:0;overflow:hidden;display:grid;gap:inherit}
.gb.fold{grid-template-rows:0fr;opacity:0}
.ch .fall{width:28px;height:28px;border-radius:9px;display:grid;place-items:center;color:var(--muted);transition:background-color var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.ch .fall:hover{background:rgba(255,255,255,.07);color:var(--text)}.ch .fall .ic{width:16px;height:16px}.ch .fall.all .ic{transform:rotate(-90deg)}
.kc{position:relative;border-radius:20px;padding:12px 13px;margin-bottom:9px;cursor:grab;background:linear-gradient(170deg,var(--card3),var(--card2));box-shadow:0 8px 16px rgba(0,0,0,.28),var(--hi);border-left:5px solid var(--cc);transition:transform .45s var(--spring),box-shadow .3s,opacity .3s}
.kc:hover{transform:translateY(-3px);box-shadow:0 14px 24px rgba(0,0,0,.36),var(--hi)}
.kc:active{cursor:grabbing}.kc.drag{opacity:.45;transform:scale(.96)}
.kc b{display:block;font-size:14px;font-weight:700;line-height:1.25;word-break:break-word}
.kc .m{font-size:12.5px;color:var(--text2);margin-top:4px;display:flex;flex-wrap:wrap;gap:4px 10px}
.kc .pill{margin-top:8px}
.kc .hrs{display:inline-block;margin:8px 0 0 6px;font-size:12.5px;color:var(--text2);font-weight:500}
.mchip{display:inline-flex;align-items:center;gap:6px;margin-top:8px;height:28px;padding:0 11px;border-radius:14px;background:rgba(52,210,123,.16);color:#9CF2C3;font-size:12.5px;font-weight:700;border:1px solid rgba(52,210,123,.4);cursor:pointer}
.mchip .ic{width:14px;height:14px}.mchip.none{background:var(--accent);color:var(--accent-text);border-color:var(--accent)}.mchip:hover{filter:brightness(1.12)}
.addm{white-space:nowrap;flex:1 0 100%;justify-content:center;order:5;margin-top:2px;display:inline-flex;align-items:center;gap:5px;height:26px;padding:0 10px;border-radius:13px;background:var(--accent);color:var(--accent-text);font-size:12px;font-weight:800}
.addm .ic{width:13px;height:13px}.kc .when{font-size:12.5px;color:var(--muted);margin-top:6px}
/* account */
.acc{display:grid;grid-template-columns:320px 1fr;gap:18px;align-items:start}
.idc{padding:26px 22px;text-align:center}
.idc .ring{width:132px;height:132px;margin:0 auto;cursor:default}.idc .ring .in-av{font-size:42px}
.idc h2{font-size:21px;font-weight:800;margin-top:14px}.idc .sub{color:var(--muted);font-size:13.5px;margin-top:3px}
.sw{display:flex;justify-content:center;gap:10px;margin:18px 0 6px}
.sw button{width:30px;height:30px;border-radius:50%;box-shadow:0 4px 8px rgba(0,0,0,.3);transition:transform .45s var(--spring),outline-color .2s;outline:3px solid transparent;outline-offset:3px}
.sw button:hover{transform:scale(1.18)}.sw button.on{outline-color:#fff}
.mini{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:20px}
.mini div{background:rgba(0,0,0,.22);border-radius:16px;padding:10px 4px}.mini b{display:block;font-size:20px}.mini span{font-size:12px;color:var(--muted);font-weight:600}
.form{padding:24px}.form h3{font-size:18px;margin-bottom:4px}
.fg{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}
.fg .inp{width:100%}
.note{font-size:12.5px;color:var(--muted);line-height:1.5}
.note code{background:rgba(0,0,0,.28);padding:1px 6px;border-radius:6px;font-size:12px;word-break:break-all}
/* floating nav */
.fnav{position:absolute;left:50%;bottom:18px;transform:translateX(-50%);z-index:20;display:flex;align-items:center;gap:10px}
.fpill{position:relative;display:flex;gap:2px;padding:6px;border-radius:30px;background:linear-gradient(160deg,var(--side1),var(--side2));box-shadow:0 14px 30px rgba(0,0,0,.45),var(--hi)}
.fpill .fbg{position:absolute;top:6px;bottom:6px;border-radius:24px;background:#EAF7EF;transition:left .55s var(--spring),width .5s var(--spring)}
.fpill button{position:relative;z-index:1;height:40px;padding:0 20px;border-radius:24px;font-weight:700;font-size:13.5px;color:#DDF0E4;transition:color .3s,transform .4s var(--spring)}
.fpill button:hover{transform:translateY(-2px);color:#fff}.fpill button:active{transform:scale(.94)}
.fpill button.on{color:#0C3320}.fpill button.on:hover{transform:none}
.fplus{width:48px;height:48px;border-radius:50%;background:linear-gradient(160deg,#4BE08F,#2BB567);color:var(--accent-text);display:grid;place-items:center;box-shadow:0 12px 24px rgba(0,0,0,.4);transition:transform .5s var(--spring)}
.fplus:hover{transform:rotate(90deg) scale(1.1)}.fplus:active{transform:scale(.88)}
/* overlay, toast, bell menu */
.ov{position:fixed;inset:0;z-index:60;display:grid;place-items:center;background:rgba(6,14,10,.62);backdrop-filter:blur(5px);opacity:0;transition:opacity .28s}
.ov.on{opacity:1}
.dlg{width:min(640px,92vw);max-height:90vh;overflow:auto;border-radius:30px;padding:24px 26px;background:linear-gradient(180deg,var(--card2),var(--card));box-shadow:0 30px 70px rgba(0,0,0,.55),var(--hi);transform:translateY(22px) scale(.9);transition:transform .55s var(--spring)}
.ov.on .dlg{transform:none}
.dlg h2{font-size:21px;font-weight:800}
.toast{position:fixed;right:30px;bottom:30px;z-index:80;display:flex;align-items:center;gap:14px;max-width:440px;padding:12px 14px 12px 20px;border-radius:24px;background:var(--card2);border:1px solid rgba(74,222,139,.45);box-shadow:0 18px 40px rgba(0,0,0,.5);font-weight:600;font-size:14px;transform:translateY(30px) scale(.9);opacity:0;pointer-events:none;transition:transform .55s var(--spring),opacity .3s}
.toast.on{transform:none;opacity:1;pointer-events:auto}.toast.bad{border-color:rgba(255,138,143,.6)}
.toast button{height:32px;padding:0 14px;border-radius:16px;background:var(--accent);color:var(--accent-text);font-weight:700;font-size:13px;transition:transform .4s var(--spring)}.toast button:hover{transform:scale(1.08)}
.bell{position:absolute;top:76px;right:28px;z-index:40;width:340px;max-height:380px;overflow:auto;padding:14px;border-radius:26px;background:var(--card2);box-shadow:0 24px 50px rgba(0,0,0,.5),var(--hi);border:1px solid var(--line);transform-origin:top right;transform:scale(.85) translateY(-8px);opacity:0;pointer-events:none;transition:transform .5s var(--spring),opacity .25s}
.bell.on{transform:none;opacity:1;pointer-events:auto}
.bell h4{font-size:15px;margin:2px 6px 8px}.bell .it{padding:10px 12px;border-radius:16px;font-size:13.5px;background:rgba(0,0,0,.2);margin-bottom:6px}.bell .it small{display:block;color:var(--muted);margin-top:2px;font-size:12px}
.spin{width:18px;height:18px;border-radius:50%;border:3px solid rgba(74,222,139,.25);border-top-color:var(--accent);animation:sp .8s linear infinite}@keyframes sp{to{transform:rotate(360deg)}}
/* money: hero tile + profits page */
.mtile{position:relative;z-index:1;display:block;width:100%;max-width:420px;text-align:left;border-radius:24px;padding:14px 18px 12px;background:rgba(5,30,16,.38);box-shadow:var(--hi),0 10px 24px rgba(0,0,0,.25);transition:transform .5s var(--spring),background .3s}
.mtile:hover{transform:translateY(-3px) scale(1.02);background:rgba(5,30,16,.52)}.mtile:active{transform:scale(.97)}
.mtile .mk{display:flex;align-items:center;justify-content:space-between;font-size:12.5px;font-weight:700;color:var(--text2)}
.mtile .mv{font-size:32px;font-weight:800;letter-spacing:-.6px;margin:2px 0 8px;color:#fff;line-height:1.15}.mtile .mv small{font-size:19px;font-weight:700;margin-right:2px;color:#9CF2C3}
.mtile .tr{height:8px;border-radius:4px;background:rgba(0,0,0,.3);overflow:hidden}.mtile .fl{height:100%;width:0;border-radius:4px;background:linear-gradient(90deg,#FFE55C,#3DDC84);transition:width 1.1s var(--spring) .45s}
.mtile .ms{font-size:12px;font-weight:600;color:var(--text2);margin-top:7px;line-height:1.35}
.mtile svg{display:block;width:100%;height:64px;margin-top:8px;overflow:visible}
.marea{opacity:0;transition:opacity 1s ease .7s}.in .marea{opacity:1}
.mproj{opacity:0;transition:opacity .8s ease 1.3s}.in .mproj{opacity:1}
.fpill button{white-space:nowrap;padding:0 13px}
.main.hasdock .fpill button{padding:0 9px;font-size:12.5px}
.pg-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px}
.dealtab{overflow-x:auto}
.dr{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(190px,1.6fr) 80px 100px 110px 120px 44px;gap:12px;align-items:center;padding:11px 20px;min-width:860px;border-top:1px solid rgba(255,255,255,.05);font-size:13.5px;transition:background .25s}
.dr.h{border-top:0;font-size:12px;font-weight:700;color:var(--muted);padding-top:2px;padding-bottom:6px}
.dr[data-id]{cursor:pointer}.dr[data-id]:hover{background:rgba(255,255,255,.04)}
.dr .num,.prow .num{font-weight:700;font-variant-numeric:tabular-nums}
.dr .sub,.prow .sub{display:block;color:var(--muted);font-size:12.5px;font-weight:500;margin-top:1px}
.ib{width:32px;height:32px;border-radius:50%;display:grid;place-items:center;background:var(--card2);color:var(--muted);transition:transform .4s var(--spring),color .25s,background .25s}
.ib:hover{transform:scale(1.12);color:var(--text);background:var(--card3)}.ib:active{transform:scale(.92)}.ib .ic{width:16px;height:16px}
.plist{max-height:236px;overflow:auto;margin:0 -6px;padding:0 6px}
.prow{display:flex;align-items:center;gap:12px;padding:10px 2px;border-top:1px solid rgba(255,255,255,.05);font-size:13.5px}.prow:first-child{border-top:0}
.cfm{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px;border-radius:15px;border:1.5px solid rgba(255,214,10,.55);background:rgba(255,214,10,.12);color:#FFE36B;font-size:12.5px;font-weight:800;white-space:nowrap;flex:none;transition:transform .15s,background .2s,border-color .2s}
.cfm:hover{background:rgba(255,214,10,.22);border-color:#FFD60A;transform:translateY(-1px)}.cfm:active{transform:scale(.95)}.cfm .ic{width:14px;height:14px}
.cfm.done{border-color:rgba(52,210,123,.45);background:rgba(52,210,123,.16);color:#7DF0A8}.cfm.done:hover{border-color:#FF9AA0;color:#FF9AA0;background:rgba(255,107,112,.12)}
.cfm[disabled]{opacity:.55;pointer-events:none}
.cfm.pulse{animation:cfmPop .45s cubic-bezier(.2,1.4,.4,1)}@keyframes cfmPop{0%{transform:scale(.85)}60%{transform:scale(1.08)}100%{transform:scale(1)}}
.tocf{border:1px solid rgba(255,214,10,.28);background:linear-gradient(180deg,rgba(255,214,10,.07),rgba(255,214,10,.02));margin-top:16px}
.tocf .hd{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}.tocf .plist{max-height:320px;overflow:auto}
.tocf .prow.gone{animation:rowOut .4s ease forwards}@keyframes rowOut{to{opacity:0;transform:translateX(24px);height:0;padding:0;margin:0}}
/* calendar */
.cal-head{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.cal-nav{display:flex;align-items:center;gap:10px}
.cal-title{font-size:22px;font-weight:800;letter-spacing:-.3px;min-width:180px;text-align:center}
.cal-filters{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.chip .cdot{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;flex:none}.chip .cdot .ic{width:12px;height:12px}
.chip.off{opacity:.45;text-decoration:line-through}
.cal-wrap{display:grid;grid-template-columns:minmax(0,2.4fr) minmax(290px,1fr);gap:16px;align-items:start}
.cal{padding:14px 14px 12px}
.cal-dow{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;font-size:12px;font-weight:700;color:var(--muted);text-align:center;margin-bottom:6px}
.cal-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));grid-auto-rows:minmax(112px,auto);gap:6px}
.cc{position:relative;border-radius:16px;padding:6px 6px 5px;background:rgba(0,0,0,.2);border:2px solid transparent;cursor:pointer;min-width:0;display:flex;flex-direction:column;gap:3px;transition:transform .35s var(--spring),background .25s,border-color .25s,box-shadow .3s}
.cc:hover{background:rgba(255,255,255,.07);transform:translateY(-2px)}
.cc.om{opacity:.5}
.cc.sel{border-color:var(--accent);box-shadow:0 0 0 3px rgba(74,222,139,.16)}
.cc .cn{font-size:12.5px;font-weight:700;color:var(--muted);padding:0 2px 1px}
.cc.td .cn span{background:var(--accent);color:var(--accent-text);border-radius:10px;padding:1px 8px}
.ce{display:flex;align-items:center;gap:5px;height:21px;padding:0 8px 0 5px;border-radius:11px;font-size:11.5px;font-weight:700;white-space:nowrap;overflow:hidden;box-shadow:0 2px 5px rgba(0,0,0,.25)}
.ce .ic{width:13px;height:13px}.ce span{overflow:hidden;text-overflow:ellipsis}
.ce.past{opacity:.55}
.cmore{font-size:11.5px;font-weight:700;color:var(--muted);padding:0 4px}
.cside{display:grid;gap:16px}.cside .card{padding:16px 18px}
.cside .hd{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px}
.crow{display:flex;align-items:center;gap:11px;padding:9px 6px;border-radius:14px;cursor:pointer;transition:background .2s}
.crow:hover{background:rgba(255,255,255,.05)}.crow.past{opacity:.6}
.crow .cb{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;flex:none;box-shadow:0 3px 8px rgba(0,0,0,.25)}.crow .cb .ic{width:17px;height:17px}
.crow .cm{min-width:0;flex:1}.crow .cm b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.crow .cm .sub{display:block;color:var(--muted);font-size:12.5px;font-weight:500;margin-top:1px}
.cdh{font-size:12px;font-weight:700;color:var(--muted);margin:12px 4px 2px}
.cscroll{max-height:340px;overflow:auto;margin:0 -6px;padding:0 6px}
.evc{display:flex;gap:9px;flex-wrap:wrap;padding:4px 2px}
.evc button{width:28px;height:28px;border-radius:50%;border:3px solid transparent;transition:transform .35s var(--spring),border-color .2s}
.evc button.on{border-color:#fff;transform:scale(1.18)}.evc button:hover{transform:scale(1.12)}
.evi{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:6px}
.evi button{height:38px;border-radius:12px;background:var(--panel);border:1px solid var(--line);display:grid;place-items:center;color:var(--muted);transition:transform .35s var(--spring),background .2s,color .2s}
.evi button:hover{transform:translateY(-2px);color:var(--text)}.evi button .ic{width:18px;height:18px}
@media (max-width:1280px){.frow{grid-template-columns:1fr 1fr 1fr}.frow>div:nth-child(4){grid-column:1/3}.stats,.cstats{grid-template-columns:1fr 1fr}.banner{grid-template-columns:1fr}.ill{display:none}.split{grid-template-columns:1fr 1.3fr}}
@media (max-width:1280px){.banner{grid-template-columns:1fr 290px}.banner>div:first-child{display:none}.cal-wrap{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition-duration:.01ms!important}}

/* ---- accounts + sync ---- */
#login{position:fixed;inset:0;z-index:90;display:none;place-items:center;background:radial-gradient(1100px 650px at 15% 0%,var(--side1),var(--bg) 70%)}
#login.on{display:grid}
.lg{width:min(420px,92vw);padding:34px 32px 30px}
.lg .mark{width:54px;height:54px;border-radius:18px;background:linear-gradient(150deg,var(--side1),var(--side2));display:grid;place-items:center;font-weight:800;font-size:22px;color:var(--accent);box-shadow:var(--sh),var(--hi)}
.lg h2{margin:16px 0 4px;font-size:24px}.lg p.sub{margin:0 0 20px;color:var(--muted);font-size:13.5px;line-height:1.5}
.lg .inp{width:100%;margin-bottom:14px}.lg .btn.pri{width:100%;margin-top:4px}
.lg .err{min-height:18px;margin:2px 4px 10px;color:var(--bad);font-size:13px;font-weight:600}
.sync{display:inline-flex;align-items:center;gap:8px;height:38px;padding:0 14px;border-radius:19px;background:var(--card2);color:var(--muted);font-size:12.5px;font-weight:600;box-shadow:var(--hi);white-space:nowrap}
.sync i{width:9px;height:9px;border-radius:50%;background:var(--g);flex:none}
.sync.syncing i{background:var(--y);animation:syp 1s ease-in-out infinite}.sync.offline i,.sync.error i{background:var(--o)}.sync.attention i,.sync.signed_out i{background:var(--r)}
@keyframes syp{50%{opacity:.3}}
@media (prefers-reduced-motion:reduce){.sync.syncing i{animation:none}}

/* ---- team dashboard ---- */
.tm{display:grid;gap:18px;padding-bottom:90px}
.tm .stale{padding:10px 16px;border-radius:16px;background:rgba(255,122,0,.14);color:#FFC48A;font-size:13px;font-weight:600}
.tm-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.tm-tile{padding:16px 18px;border-radius:22px;background:linear-gradient(180deg,var(--card),var(--card-end));box-shadow:var(--sh),var(--hi)}
.tm-tile span{display:block;font-size:12.5px;font-weight:600;color:var(--muted)}.tm-tile b{display:block;font-size:30px;margin:4px 0 2px;letter-spacing:-.5px}.tm-tile small{color:var(--muted);font-size:12px}
.tm-bar{height:7px;border-radius:4px;background:rgba(255,255,255,.07);overflow:hidden;margin-top:8px}.tm-bar i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,#34D27B,#7BF0AE);transition:width .6s var(--smooth)}
.tm-people{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px}
.tm-p{padding:18px 20px}.tm-p.me{outline:2px solid rgba(74,222,139,.45)}
.tm-p h3{margin:0;font-size:17px;display:flex;align-items:center;gap:10px}
.tav{width:38px;height:38px;border-radius:50%;flex:none;display:grid;place-items:center;font-size:14px;font-weight:800;color:#fff;background:linear-gradient(150deg,var(--accent-soft),var(--av-bg));box-shadow:0 0 0 2px rgba(255,255,255,.12)}
.avbtns{display:flex;gap:8px;justify-content:center;margin-top:12px}
.tm-p .role{font-size:11px;font-weight:700;padding:3px 8px;border-radius:9px;background:rgba(255,255,255,.08);color:var(--muted)}
/* call streaks */
.stk{display:inline-flex;align-items:center;gap:3px;height:22px;padding:0 8px 0 5px;border-radius:11px;font-size:12px;font-weight:800;line-height:1;vertical-align:middle;
  background:var(--sc);color:var(--st);box-shadow:0 0 12px color-mix(in srgb,var(--sc) 45%,transparent);white-space:nowrap;margin-left:6px;letter-spacing:0}
.stk .ic{width:13px;height:13px}.stk .ic svg{stroke-width:2.4}
.stk.low{background:rgba(255,255,255,.08);color:var(--text2);box-shadow:none}
.stk.none{background:rgba(255,255,255,.05);color:var(--faint);box-shadow:none}
.stk.big{height:28px;padding:0 11px 0 8px;font-size:14px;border-radius:14px}.stk.big .ic{width:16px;height:16px}
.tm-stkc{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.stk-cap{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);margin-bottom:6px;min-width:0}
.stk-cap .stk{margin-left:0;flex:none}.stk-cap>span:first-child{flex:none;display:inline-flex}.stk-cap>span:first-child .ic{width:15px;height:15px}.stk-cap span:not(.stk){min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.stk-cap span.ok{color:var(--accent-hi)}
.stk-cap small{margin-left:auto;font-size:11px;color:var(--faint);flex:none}
.tm-stkc .stk-bar{height:26px;margin:0 12px 0 2px}
.tm-stkc .stk-m{width:23px;height:23px;margin:-11.5px 0 0 -11.5px;font-size:9.5px}
.tm-stkc .stk-track{height:8px;margin-top:-4px}
.stk-h{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.stk-h .muted{font-size:12.5px;margin-top:3px;max-width:620px;line-height:1.45}
.stk-r{display:grid;grid-template-columns:minmax(170px,240px) minmax(0,1fr);gap:8px 18px;align-items:center;padding:14px 2px;border-top:1px solid var(--line)}
.stk-r:first-of-type{border-top:0}
.stk-who{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 10px;align-items:center;cursor:pointer}
.stk-who .tav{grid-row:1/3;width:36px;height:36px;font-size:13px}
.stk-who b{font-size:14px;display:flex;align-items:center;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.stk-who small{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stk-who small.ok{color:var(--accent-hi)}
.stk-bar{position:relative;height:30px;margin-right:15px;margin-left:2px}
.stk-track{position:absolute;left:0;right:0;top:50%;height:10px;margin-top:-5px;border-radius:5px;background:rgba(255,255,255,.07);overflow:hidden}
.stk-track i{position:absolute;inset:0;border-radius:5px;clip-path:inset(0 var(--w) 0 0 round 5px);transition:clip-path 1.1s var(--e-out)}
.stk-track i.go{clip-path:inset(0 100% 0 0 round 5px)}
.stk-m{position:absolute;top:50%;width:28px;height:28px;margin:-14px 0 0 -14px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:800;
  background:#1d2a23;color:var(--faint);border:2px solid rgba(255,255,255,.08);transition:transform var(--d-card) var(--e-spring),background-color .4s,color .4s}
.stk-m.on{background:var(--sc);color:var(--st);border-color:color-mix(in srgb,var(--sc) 60%,#fff);box-shadow:0 0 14px color-mix(in srgb,var(--sc) 55%,transparent)}
.stk-m.next{border-color:var(--sc);color:var(--text2);border-style:dashed}
.stk-r:hover .stk-m.on{transform:scale(1.08)}
.stk-legend{display:flex;flex-wrap:wrap;gap:6px}
.stk-legend span{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:var(--muted);padding:3px 8px 3px 4px;border-radius:10px;background:rgba(0,0,0,.18)}
.stk-legend i{width:12px;height:12px;border-radius:50%;background:var(--sc)}
.hcard h4 .stk,.pcard h2 .stk{margin-left:8px}
@media (max-width:860px){
  .stk-r{grid-template-columns:minmax(0,1fr);gap:10px}
  .stk-bar{margin:0 14px 0 14px}
  .stk-m{width:26px;height:26px;margin:-13px 0 0 -13px;font-size:10.5px}
}
.tm-p .st,.tm-p .st:hover{height:auto;min-height:0;padding:0;border:0;border-radius:0;background:none;box-shadow:none;transform:none;filter:none;line-height:1.2}
.tm-p .st{margin-left:auto;font-size:12px;font-weight:600;color:var(--muted);display:flex;align-items:center;gap:6px}.tm-p .st i{width:8px;height:8px;border-radius:50%;background:#6b7d72}.tm-p .st.on i{background:var(--g)}
.tm-p .nums{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin:14px 0 4px;text-align:center}.tm-p .nums b{display:block;font-size:20px}.tm-p .nums span{font-size:10.5px;color:var(--muted);font-weight:600}
.tm-p .last{margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.4;min-height:34px}
.tm-2{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:18px}
@media (max-width:1100px){.tm-2{grid-template-columns:1fr}}
.tm-card{padding:20px 22px}.tm-card h3{margin:0 0 14px;font-size:16px}
.tm-feed{display:grid;gap:2px;max-height:380px;overflow:auto}.tm-feed div{padding:9px 4px;border-bottom:1px solid rgba(255,255,255,.05);font-size:13.5px;line-height:1.4}.tm-feed small{display:block;color:var(--muted);font-size:11.5px}
.tm-chart{display:flex;align-items:flex-end;gap:6px;height:140px;margin-top:6px}.tm-chart div{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:6px;height:100%}
.tm-chart i{width:100%;min-height:3px;border-radius:6px 6px 3px 3px;background:linear-gradient(180deg,#5BEB9C,#2BB567)}.tm-chart div.today i{background:linear-gradient(180deg,#FFD60A,#E0B000)}.tm-chart small{font-size:10px;color:var(--muted)}
.tm table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:14px}.tm th,.tm td{padding:8px 6px;text-align:right;border-bottom:1px solid rgba(255,255,255,.05)}.tm th:first-child,.tm td:first-child{text-align:left}.tm th{color:var(--muted);font-weight:600;font-size:12px}
/* ===== notes / scripts / dock / call log / admin ===== */
.nt{display:grid;grid-template-columns:300px minmax(0,1fr);gap:16px;height:100%;min-height:0;padding-bottom:84px}
.nt-list{display:flex;flex-direction:column;min-height:0;padding:14px}
.nt-top{display:grid;gap:10px;margin-bottom:10px}
.nt-top .inp{width:100%}
.nt-new{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.nt-chips{display:flex;gap:6px;flex-wrap:wrap}
.nt-chips .chip{height:30px;padding:0 12px;font-size:12.5px}
.nt-items{flex:1;min-height:0;overflow:auto;margin:0 -6px;padding:0 6px}
.nt-sec{font-size:11.5px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:12px 4px 6px}
.nt-it{display:block;width:100%;text-align:left;padding:10px 12px;border-radius:16px;margin-bottom:4px;transition:background .2s}
.nt-it:hover{background:rgba(255,255,255,.06)}.nt-it.on{background:rgba(74,222,139,.16);box-shadow:inset 0 0 0 1px rgba(74,222,139,.45)}
.nt-it b{display:block;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nt-it small{display:flex;gap:6px;align-items:center;color:var(--muted);font-size:12px;margin-top:2px;overflow:hidden;white-space:nowrap}
.tag{display:inline-block;padding:1px 8px;border-radius:9px;font-size:11px;font-weight:700;background:rgba(255,255,255,.1);color:var(--muted)}
.tag.team{background:rgba(92,157,255,.22);color:#A9CBFF}.tag.me{background:rgba(74,222,139,.16);color:#9CF2C3}.tag.scr{background:rgba(255,214,10,.18);color:#FFE27A}
.nt-ed{display:flex;flex-direction:column;min-height:0;padding:16px 18px;gap:10px}
.ed-head{display:flex;gap:12px;align-items:center}
.ed-title{flex:1;min-width:0;height:46px;font-size:22px;font-weight:800;border-radius:14px;border:1px solid transparent;background:transparent;padding:0 10px;color:var(--text)}
.ed-title:hover,.ed-title:focus{border-color:var(--line);background:var(--panel);outline:0}
.seg{display:inline-flex;border-radius:18px;background:var(--panel);border:1px solid var(--line);padding:3px}
.seg button{height:30px;padding:0 14px;border-radius:15px;font-size:12.5px;font-weight:700;color:var(--muted)}
.seg button.on{background:var(--accent);color:var(--accent-text)}.seg button[disabled]{opacity:.5;cursor:default}
.ed-meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px;color:var(--muted)}
.ed-meta .sp{flex:1}.ed-meta .inp{height:32px;font-size:12.5px;width:150px}
.sv{font-weight:700}.sv.bad{color:var(--bad)}
.tb{display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px;border-radius:16px;background:var(--panel);border:1px solid var(--line)}
.tb button,.tb .tbc{min-width:32px;height:32px;padding:0 8px;border-radius:10px;display:inline-grid;place-items:center;font-size:14px;font-weight:700;color:var(--text);cursor:pointer;position:relative}
.tb button:hover,.tb .tbc:hover{background:rgba(255,255,255,.1)}.tb button.on{background:var(--accent);color:var(--accent-text)}
.tb select{height:32px;border-radius:10px;font-size:12.5px;padding-left:8px}
.tb i.sep{width:1px;height:22px;background:var(--line);margin:0 4px}
.tb .tbc input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.tb .tbc .a{border-bottom:4px solid var(--tbc,#fff);line-height:15px}
.tb svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round}
.lnkbar{display:none;gap:8px;align-items:center}.lnkbar.on{display:flex}.lnkbar .inp{flex:1;height:34px}
.paper{flex:1;min-height:0;overflow:auto;border-radius:18px;background:#F7FAF8;color:#17251D}
.rte{outline:0;padding:26px 34px 60px;min-height:100%;line-height:1.55;font-size:16px;word-wrap:break-word;overflow-wrap:anywhere}
.rte h1{font-size:2em;margin:.6em 0 .3em}.rte h2{font-size:1.5em;margin:.6em 0 .3em}.rte h3{font-size:1.2em;margin:.6em 0 .3em}
.rte p,.rte div{margin:0 0 .55em}.rte ul,.rte ol{margin:0 0 .6em 1.4em;padding-left:.8em}.rte blockquote{border-left:4px solid #BFD8C8;margin:0 0 .6em;padding-left:14px;color:#3b5246}
.rte a{color:#1558D6;text-decoration:underline;cursor:pointer}.rte mark{background:#FFE27A}
.rte.read{line-height:1.7}
.ntxt{flex:1;min-height:0;width:100%;resize:none;border-radius:18px;border:1px solid var(--line);background:#F7FAF8;color:#17251D;padding:22px 26px;font:inherit;font-size:16px;line-height:1.6}
.ntxt:focus{outline:0;border-color:var(--accent)}
.nt-empty{display:grid;place-items:center;height:100%;color:var(--muted);text-align:center;padding:30px;line-height:1.6}
body.focus .side,body.focus .top,body.focus .fnav,body.focus .nt-list{display:none}
body.focus .app{grid-template-columns:1fr}body.focus .nt{grid-template-columns:1fr;padding-bottom:0}
/* docked script */
.dock{display:none;position:absolute;top:0;right:0;bottom:0;width:var(--dockw,380px);z-index:15;flex-direction:column;gap:8px;padding:0 20px 14px 10px}
.main.hasdock .dock{display:flex}.main.hasdock .page{right:var(--dockw,380px)}.main.hasdock .fnav{left:calc((100% - var(--dockw,380px))/2)}
.dk-grip{position:absolute;left:-2px;top:20px;bottom:20px;width:12px;cursor:col-resize;z-index:2}
.dk-grip::after{content:"";position:absolute;left:5px;top:50%;height:46px;width:4px;margin-top:-23px;border-radius:2px;background:var(--line)}
.dk-head{display:flex;gap:6px;align-items:center;padding-top:8px}.dk-head select{flex:1;min-width:0;height:36px}
.dk-head button{min-width:34px;height:34px;border-radius:12px;background:var(--card2);font-weight:800;font-size:13px}
.dk-head button:hover{background:var(--card3)}
.dk-body{flex:1;min-height:0}.dk-body .paper{height:100%}
.dk-find{height:34px;border-radius:12px;border:1px solid var(--line);background:var(--panel);padding:0 12px;font-size:13px;width:100%}
mark.hit{background:#FFD60A;color:#111;border-radius:3px}
.rb.on{box-shadow:0 0 0 3px rgba(255,255,255,.35),0 8px 16px rgba(0,0,0,.3)}
/* call log */
.cl{display:grid;gap:14px;padding-bottom:90px}
.cl-f{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;padding:14px 16px}
.cl-f>div{display:grid;gap:4px}.cl-f .inp,.cl-f select{height:38px}
.cl-sum{display:flex;gap:8px;flex-wrap:wrap}
.op{display:inline-block;padding:3px 11px;border-radius:12px;font-size:12px;font-weight:800;white-space:nowrap}
.cl-sum button{display:inline-flex;gap:8px;align-items:center;padding:5px 12px 5px 6px;border-radius:18px;background:var(--panel);border:1px solid var(--line);font-size:13px;font-weight:700}
.cl-sum button.on{border-color:var(--accent)}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}.tbl th{text-align:left;color:var(--muted);font-size:12px;font-weight:700;padding:8px 12px;position:sticky;top:0;background:var(--card)}
.tbl td{padding:9px 12px;border-top:1px solid rgba(255,255,255,.05);vertical-align:top}.tbl tr:hover td{background:rgba(255,255,255,.03)}
.tbl .nt2{color:var(--muted);max-width:340px;white-space:pre-wrap}
/* call log motion: rows cascade in, new calls glow, chips pop, numbers count up */
#clBody .tbl tr.rin{animation:clRow .52s var(--e-out) both;animation-delay:calc(var(--i,0)*26ms)}
@keyframes clRow{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
#clBody .tbl tr.fresh td{animation:clFresh 2.4s var(--e-out)}
@keyframes clFresh{0%,25%{background:rgba(74,222,139,.16)}100%{background:transparent}}
#clBody .tbl tr td{transition:background-color var(--d-hover) var(--e-out)}
#clBody .tbl tr:hover td{background:rgba(74,222,139,.06)}
#clBody .tbl tr .op{transition:transform var(--d-pop) var(--e-spring)}#clBody .tbl tr:hover .op{transform:scale(1.06)}
#clBody{transition:opacity var(--d-hover) var(--e-out)}#clBody.busy{opacity:.55}
.cl-sum button{transition:transform var(--d-card) var(--e-spring),border-color var(--d-hover) var(--e-out),background-color var(--d-hover) var(--e-out)}
.cl-sum button:hover{transform:translateY(-2px)}.cl-sum button:active{transform:scale(.95)}
.cl-sum button.on{background:rgba(74,222,139,.10)}
.cl-sum button.cin{animation:clChip .5s var(--e-spring) both;animation-delay:calc(var(--i,0)*45ms)}
@keyframes clChip{from{opacity:0;transform:translateY(8px) scale(.9)}to{opacity:1;transform:none}}
.cl-sk{display:grid;gap:10px;padding:10px 6px}.cl-sk i{display:block;height:38px;border-radius:12px;background:linear-gradient(90deg,rgba(255,255,255,.04),rgba(255,255,255,.09),rgba(255,255,255,.04));background-size:200% 100%;animation:slide 1.3s linear infinite}
.cl-sk i:nth-child(2){opacity:.8}.cl-sk i:nth-child(3){opacity:.6}.cl-sk i:nth-child(4){opacity:.4}.cl-sk i:nth-child(5){opacity:.25}
#clBody .empty{animation:clRow .5s var(--e-out) both}
#clLog .ic{transition:transform var(--d-card) var(--e-spring)}#clLog:hover .ic{transform:rotate(90deg)}
.oc{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:6px 0 14px}
.oc button{padding:10px 12px;border-radius:14px;background:var(--panel);border:2px solid var(--line);text-align:left;font-weight:700;font-size:13.5px;display:flex;gap:8px;align-items:center}
.oc button.on{border-color:var(--accent);background:rgba(74,222,139,.12)}
.oc button i{width:12px;height:12px;border-radius:50%;flex:none}
/* admin */
.ad{display:grid;gap:16px;padding-bottom:90px}
.ad .card{padding:18px 20px}.ad h3{margin-bottom:10px}
.ad-t{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:10px 0 14px}
.ad-t .inp{width:100%}
.tg{position:relative;width:46px;height:26px;border-radius:13px;background:#44574c;transition:background .25s;flex:none}
.tg::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;transition:transform .3s var(--spring)}
.tg.on{background:var(--accent)}.tg.on::after{transform:translateX(20px)}
/* calendar views / done */
.cal-views{display:inline-flex;gap:6px}
.wk{padding:12px}.wk-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}
.cal-wrap.v-week{grid-template-columns:1fr}.cal-wrap.v-week .cside{grid-template-columns:1fr 1fr}.cal-wrap.v-week .wcol .crow{flex-wrap:wrap}.wcol .crow .cdn{width:22px;height:22px;font-size:12px}
.wcol{border-radius:18px;background:rgba(255,255,255,.03);padding:8px;display:flex;flex-direction:column;gap:4px;min-height:260px}
.wcol.td{box-shadow:inset 0 0 0 2px rgba(74,222,139,.55)}.wcol.sel{background:rgba(74,222,139,.09)}
.wcol .wh{display:flex;justify-content:space-between;align-items:baseline;cursor:pointer;padding:2px 4px;color:var(--muted);font-weight:700;font-size:12.5px}.wcol .wh b{font-size:20px;color:var(--text)}
.wcol .wl{flex:1;display:grid;gap:2px;align-content:start}.wcol .wn{font-size:12px;padding:4px}
.wcol .crow{padding:6px 4px;gap:8px}.wcol .crow .cb{width:26px;height:26px}.wcol .crow .cb .ic{width:13px;height:13px}.wcol .crow .cm b{font-size:12.5px;white-space:normal}.wcol .crow .cm .sub{font-size:11px;white-space:normal}
.dy{padding:14px 16px}.dyr{display:grid;grid-template-columns:78px 1fr;gap:8px;align-items:center;border-top:1px solid rgba(255,255,255,.05)}.dyr .dt{color:var(--muted);font-size:12.5px;font-weight:700}
.cdn{width:28px;height:28px;border-radius:50%;border:2px solid var(--line);color:transparent;display:grid;place-items:center;font-size:14px;font-weight:900;flex:none;transition:all .25s}
.cdn:hover{border-color:var(--accent);color:var(--accent)}.cdn.on{background:var(--accent);border-color:var(--accent);color:var(--accent-text)}
.crow.dn .cm b{text-decoration:line-through;opacity:.6}
.evt{display:flex;gap:6px;flex-wrap:wrap}
.tm-p .tk{font-size:12px;color:var(--muted);margin-top:6px}

/* ---- profile extras, updates ---- */
.accr{display:grid;gap:18px;min-width:0}
.pban{aspect-ratio:4/1;border-radius:18px;background:linear-gradient(120deg,#1D4130,#173A28);background-size:cover;background-position:center;position:relative}
.pbanw{margin-bottom:6px}.pbanw .avbtns{justify-content:flex-start}
.moods{display:flex;gap:6px;flex-wrap:wrap}.moods button{width:38px;height:38px;border-radius:12px;background:var(--panel);border:1px solid var(--line);font-size:19px}.moods button.on{border-color:var(--accent);background:rgba(74,222,139,.16)}
textarea.inp{height:auto;padding:10px 14px;line-height:1.45;resize:vertical;font:inherit}
.upd{display:flex;gap:16px;align-items:center;justify-content:space-between;margin-top:10px;flex-wrap:wrap}.upd .note{margin-top:3px}
.upd .bar{height:6px;border-radius:3px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:8px;display:none}.upd .bar i{display:block;height:100%;background:var(--accent);width:0}
.tm-th{padding:16px 20px}.tm-th h3{margin:0 0 10px;font-size:16px}
.th-i{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid rgba(255,255,255,.06)}.th-i:first-of-type{border-top:0}
.th-i q{font-size:14.5px;line-height:1.4;quotes:"\201C" "\201D"}.th-i small{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.tm-p{cursor:pointer;border-top:3px solid var(--acc,transparent)}
.tm-p .psub{color:var(--muted);font-size:12.5px;margin:6px 0 0}.tm-p .pbio{font-size:13px;line-height:1.4;margin-top:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:#cfe3d6}
.tm-p .pth{margin-top:8px;padding:8px 10px;border-radius:12px;background:rgba(255,255,255,.06);font-size:13px;line-height:1.35}
.pcard{--acc:#3DDC84;text-align:center}.pcard .pban{margin:-24px -26px 0;border-radius:30px 30px 0 0}
.pcard .pav{margin-top:-42px;display:flex;justify-content:center;position:relative;z-index:2}.pcard .pav .tav{width:84px;height:84px;font-size:28px;box-shadow:0 0 0 4px #182A1F,0 0 0 6px var(--acc)}
.pcard h2{margin-top:10px;font-size:22px}.pcard .pm{font-size:22px}.pcard .sub{color:var(--muted);font-size:13.5px;margin-top:2px}.pcard .sub .on{color:var(--accent)}
.pcard .pbio2{margin:14px 4px 0;line-height:1.5;white-space:pre-wrap;font-size:14px}
.pcard .pth{margin:14px 0 0;padding:12px 14px;border-radius:16px;background:rgba(255,255,255,.07);font-size:15px;line-height:1.4}.pcard .pth small{display:block;color:var(--muted);font-size:11.5px;margin-top:4px}
.idc .pban{margin:-26px -22px 14px;border-radius:30px 30px 0 0}.idc .pban+.ring{margin-top:-52px}.idc .ring{position:relative;z-index:2}
/* ---- phones and tablets (also used by the iPhone home-screen app) ---- */
@media (max-width:860px){
  html,body{height:100%}
  .app{display:block;padding:0;height:100dvh}
  .side{display:none}
  .main{border-radius:0;height:100dvh;padding-top:env(safe-area-inset-top)}
  .top{padding:10px 12px 4px;gap:8px}
  .top h1{font-size:19px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;flex:1}
  .srch,#userBtn,#scriptBtn{display:none}
  .sync{height:34px;padding:0 10px;font-size:12px}.sync span{max-width:92px;overflow:hidden;text-overflow:ellipsis}
  .page{padding:8px 12px calc(92px + env(safe-area-inset-bottom))}
  .fnav{left:0;right:0;bottom:0;transform:none;padding:8px 8px calc(8px + env(safe-area-inset-bottom));background:rgba(12,22,17,.94);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);box-shadow:0 -8px 24px rgba(0,0,0,.35)}
  .fpill{overflow-x:auto;max-width:100%;scrollbar-width:none;border-radius:26px;width:100%}.fpill::-webkit-scrollbar{display:none}
  .fpill button{height:38px;padding:0 14px;font-size:13px;flex:none}
  .fplus{display:none}
  .banner{grid-template-columns:1fr;padding:18px}.banner>div:first-child,.ill{display:none}
  .stats,.cstats{grid-template-columns:1fr 1fr;gap:10px}
  .frow{grid-template-columns:1fr 1fr}.frow>div:nth-child(4){grid-column:1/3}
  .split{min-height:0}.split .dpane{display:none}
  .board{grid-template-columns:repeat(4,minmax(240px,82vw));overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:8px}.board>*{scroll-snap-align:start}
  .page{overflow-x:hidden}
  .two,.pg-head{grid-template-columns:minmax(0,1fr)!important}.two>*,.pg-head>*,.ad>*,.cl>*,.tm>*,.acc>*,.accr>*{min-width:0;max-width:100%}
  .ad,.cl,.tm{grid-template-columns:minmax(0,1fr)}.pg-head{display:grid!important;gap:10px}
  .dealtab,.tbl-w{overflow-x:auto}.dr{min-width:0}
  .ad .tbl{display:block}.ad .card{overflow-x:auto}
  .acc{grid-template-columns:minmax(0,1fr)}
  .fg{grid-template-columns:minmax(0,1fr)}.fg>*{grid-column:auto!important}
  .tm-2,.cal-wrap,.nt,.split{grid-template-columns:minmax(0,1fr)}
  .nt{height:auto;padding-bottom:96px}.nt-list{max-height:260px}
  .ad-t{grid-template-columns:1fr 1fr}
  .tm-tiles{grid-template-columns:1fr 1fr}.tm-people{grid-template-columns:minmax(0,1fr)}
  .ad-t,.stats,.cstats{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.cl-f .inp,.cl-f select{width:100%}
  .tm-p .nums{grid-template-columns:repeat(3,1fr)}
  .dlg{width:94vw;padding:20px 18px;border-radius:24px;max-height:86dvh}
  .tbl{display:block;overflow-x:auto;white-space:nowrap}
  #clBody .tbl{display:block;white-space:normal}#clBody .tbl tbody{display:grid;gap:10px}
  #clBody .tbl tr:first-child{display:none}
  #clBody .tbl tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;padding:12px 14px;border-radius:18px;background:rgba(0,0,0,.18);border:1px solid var(--line)}
  #clBody .tbl td{padding:0;border:0;background:none!important}
  #clBody .tbl tr.fresh{animation:clFreshM 2.4s var(--e-out)}@keyframes clFreshM{0%,25%{border-color:var(--accent);box-shadow:0 0 0 3px rgba(74,222,139,.18)}100%{}}
  #clBody .tbl tr{transition:transform var(--d-card) var(--e-spring),border-color var(--d-hover) var(--e-out)}#clBody .tbl tr:active{transform:scale(.985)}
  #clBody .tbl td:nth-child(1){grid-column:1;color:var(--muted);font-size:12.5px}#clBody .tbl td:nth-child(5){grid-column:2;grid-row:1/3;align-self:center}
  #clBody .tbl td:nth-child(2){grid-column:1;font-size:12.5px;color:var(--muted)}#clBody .tbl td:nth-child(3){grid-column:1/-1;font-size:14.5px}
  #clBody .tbl td:nth-child(4){grid-column:1/-1;font-size:13px}#clBody .tbl td:nth-child(6){grid-column:1/-1;max-width:none}#clBody .tbl td:nth-child(6):empty{display:none}
  .cl-f{padding:12px}.cl-f>div{flex:1 1 140px}
  .wk-grid{grid-template-columns:repeat(7,minmax(130px,1fr))}
  .dock{display:none!important}
  .toast{bottom:calc(84px + env(safe-area-inset-bottom))}
  input,select,textarea{font-size:16px}
}
.web .frow,.web #fplus{display:none}
.web #goBtn{display:none}

/* ---- bottom navbar: outline + sliding indicator ---- */
.fpill{box-shadow:0 0 0 1.5px rgba(124,240,176,.5),0 0 24px rgba(74,222,139,.22),0 14px 30px rgba(0,0,0,.45);transition:box-shadow .5s}
.fpill:hover{box-shadow:0 0 0 1.5px rgba(160,255,200,.85),0 0 30px rgba(74,222,139,.36),0 14px 30px rgba(0,0,0,.45)}
.fthumb{position:absolute;bottom:2px;height:4px;border-radius:2px;background:linear-gradient(90deg,#7BF0B0,#34D27B);box-shadow:0 0 10px rgba(74,222,139,.8);transition:left .6s var(--spring),width .5s var(--spring);pointer-events:none;z-index:2}
/* ---- called leads filters ---- */
.cflt{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:flex-end}.cflt select{height:38px}
.cby{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:12px;color:var(--muted);font-weight:600}
.cby i{width:18px;height:18px;border-radius:50%;background:linear-gradient(150deg,#3DDC85,#173A28);display:grid;place-items:center;font-style:normal;font-size:9px;font-weight:800;color:#fff;flex:none}
.mchip.setup{background:var(--accent);color:var(--accent-text);border-color:var(--accent)}
@media (max-width:860px){.fthumb{bottom:3px}.cflt{justify-content:flex-start}.cflt select{flex:1 1 calc(50% - 8px);min-width:0}}

/* =====================================================================
   LEAFLINE 11 — design system layer: glass, light, motion, new features
   Everything here reads the tokens in :root, so the three themes follow.
   ===================================================================== */
html{scroll-behavior:smooth}
::selection{background:var(--accent-soft);color:var(--text)}
.page{scroll-behavior:smooth;overscroll-behavior:contain}
/* --- motion defaults: nothing linear, nothing abrupt --- */
button,.btn,.chip,.ib,.rb,.nv,select,.inp,.kc,.li,.card,.stat,.cstat,.tm-p,.tm-tile,.lbr,.post,.badge-i{transition-timing-function:var(--e-out)}
.btn,.chip,.ib,.rb{transition:transform var(--d-card) var(--e-spring),background-color var(--d-hover) var(--e-out),box-shadow var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out),border-color var(--d-hover) var(--e-out),filter var(--d-hover) var(--e-out)}
.btn:hover{box-shadow:var(--hi),0 10px 22px rgba(0,0,0,.28),0 0 0 1px var(--accent-line),0 0 22px var(--glow-soft)}
.btn:active,.chip:active,.ib:active,.rb:active{transform:scale(.95);transition-duration:var(--d-micro)}
.btn.pri{background:linear-gradient(160deg,var(--accent),var(--accent2));color:var(--accent-text);box-shadow:var(--hi),0 8px 22px var(--glow-soft)}
.btn.pri:hover{background:linear-gradient(160deg,var(--accent-hi),var(--accent));box-shadow:var(--hi),0 12px 28px var(--glow),0 0 0 1px var(--accent-line)}
.btn.stop{background:linear-gradient(160deg,#F2A0A0,var(--bad));color:#2A0909}
.chip.on{background:var(--accent-soft);border-color:var(--accent-line);color:var(--accent-hi);box-shadow:0 0 16px var(--glow-soft)}
.chip:hover{border-color:var(--line2);box-shadow:0 0 14px var(--glow-soft)}
select:focus,.inp:focus{border-color:var(--accent-line);box-shadow:0 0 0 4px var(--accent-soft),0 0 18px var(--glow-soft)}
:focus-visible{outline:2px solid var(--accent-line);outline-offset:3px;box-shadow:0 0 0 5px var(--accent-soft)}
.card{border:1px solid var(--line);transition:box-shadow var(--d-card) var(--e-out),border-color var(--d-card) var(--e-out),transform var(--d-card) var(--e-spring)}
.stat,.cstat,.tm-p,.tm-tile,.kc,.lbr,.post,.pod{will-change:auto}
.stat:hover,.cstat:hover,.tm-p:hover,.tm-tile:hover,.post:hover,.kc:hover{box-shadow:var(--sh),0 0 0 1px var(--accent-line),0 0 30px var(--glow-soft)}
.empty .bub{animation:float 3.4s var(--e-io) infinite}
.spin{animation-timing-function:cubic-bezier(.5,.15,.5,.85)}
img.fade{opacity:0;transition:opacity var(--d-card) var(--e-out)}img.fade.ok{opacity:1}
/* status tones: soft tints, never solid colour on colour */
.st{box-shadow:var(--hi);border:1px solid transparent}
.st.g{background:rgba(63,212,135,.16);color:#8DF0BB;border-color:rgba(63,212,135,.35)}
.st.y{background:rgba(233,193,90,.15);color:#F1D58C;border-color:rgba(233,193,90,.35)}
.st.o{background:rgba(235,149,90,.15);color:#F4BC8F;border-color:rgba(235,149,90,.35)}
.st.r{background:rgba(228,111,111,.15);color:#F3A3A3;border-color:rgba(228,111,111,.35)}
.st:hover{filter:none;box-shadow:0 0 18px var(--glow-soft)}
.st.cur{outline:2px solid var(--accent-line);outline-offset:2px;box-shadow:0 0 18px var(--glow-soft)}
.s1,.s2,.s3,.s4{background:linear-gradient(160deg,var(--card2),var(--card-end))}
.stat .ico,.cstat .ico{background:var(--tone-bg,var(--accent-soft))!important;color:var(--tone,var(--accent))!important;box-shadow:0 0 0 1px var(--tone-line,var(--accent-line)),0 0 18px var(--tone-glow,var(--glow-soft))}
.stat .ico .ic,.cstat .ico .ic{color:inherit}
.stat .lb,.stat .dl{color:var(--text2)}
.tone-g{--tone:#7BEBAE;--tone-bg:rgba(63,212,135,.14);--tone-line:rgba(63,212,135,.34);--tone-glow:rgba(63,212,135,.18)}
.tone-y{--tone:#EDCB74;--tone-bg:rgba(233,193,90,.13);--tone-line:rgba(233,193,90,.32);--tone-glow:rgba(233,193,90,.14)}
.tone-o{--tone:#F1AE7C;--tone-bg:rgba(235,149,90,.13);--tone-line:rgba(235,149,90,.32);--tone-glow:rgba(235,149,90,.14)}
.tone-r{--tone:#EE9696;--tone-bg:rgba(228,111,111,.13);--tone-line:rgba(228,111,111,.32);--tone-glow:rgba(228,111,111,.14)}
.cstat{background:linear-gradient(160deg,var(--card2),var(--card-end))!important;border:1px solid var(--line)}
.kc{border-left-width:3px}
.mchip{background:var(--accent-soft);color:var(--accent-hi);border-color:var(--accent-line)}
.mchip.setup,.mchip.none,.addm{background:linear-gradient(160deg,var(--accent),var(--accent2));color:var(--accent-text);border-color:transparent;box-shadow:0 6px 16px var(--glow-soft)}
.mchip:hover,.addm:hover{filter:none;box-shadow:0 0 0 1px var(--accent-line),0 0 18px var(--glow)}
.toast{background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border-color:var(--accent-line);box-shadow:var(--sh-lg),0 0 30px var(--glow-soft);transition:transform var(--d-card) var(--e-spring),opacity var(--d-pop) var(--e-out)}
.toast button{background:linear-gradient(160deg,var(--accent),var(--accent2))}
/* dialogs: glass sheet, smooth in and out */
.ov{z-index:var(--z-modal);background:rgba(4,10,7,.55);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);transition:opacity var(--d-pop) var(--e-out)}
.dlg{border:1px solid var(--line);box-shadow:var(--sh-lg),0 0 0 1px rgba(255,255,255,.02),0 0 60px var(--glow-soft),var(--hi);transition:transform var(--d-card) var(--e-spring),opacity var(--d-pop) var(--e-out);opacity:0}
.ov.on .dlg{opacity:1}
.bell{background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border-color:var(--line2);box-shadow:var(--sh-lg),0 0 30px var(--glow-soft);transition:transform var(--d-pop) var(--e-spring),opacity var(--d-pop) var(--e-out)}
/* top bar round buttons: glass, not solid green */
.rb{background:linear-gradient(160deg,var(--card3),var(--card2));color:var(--accent-hi);box-shadow:var(--hi),0 6px 14px rgba(0,0,0,.25),0 0 0 1px var(--line)}
.rb:hover{transform:translateY(-2px);background:linear-gradient(160deg,var(--card3),var(--card3));color:#fff;box-shadow:var(--hi),0 10px 20px rgba(0,0,0,.3),0 0 0 1px var(--accent-line),0 0 22px var(--glow)}
.rb .cnt{background:var(--accent);color:var(--accent-text);box-shadow:0 0 12px var(--glow)}
.sync{background:var(--card2);border:1px solid var(--line)}
.srch input{background:var(--card);border-color:var(--line)}
.srch input:focus{border-color:var(--accent-line);box-shadow:0 0 0 4px var(--accent-soft),0 0 24px var(--glow-soft),inset 0 2px 6px rgba(0,0,0,.28)}
/* ---------- sidebar: glass, illuminated edge instead of a white pill ---------- */
.side{background:linear-gradient(170deg,var(--side1),var(--side2));border:1px solid var(--line)}
.side:before{background:radial-gradient(260px 200px at 20% 0,rgba(255,255,255,.08),transparent 70%)}
.ring{background:conic-gradient(from 200deg,var(--accent),var(--accent-hi),var(--accent));box-shadow:0 8px 20px rgba(0,0,0,.3),0 0 26px var(--glow-soft);transition:transform var(--d-card) var(--e-spring),box-shadow var(--d-card) var(--e-out)}
.ring:hover{transform:scale(1.05);box-shadow:0 10px 24px rgba(0,0,0,.3),0 0 36px var(--glow)}
.ring .in-av{position:relative;overflow:hidden}
.ring .dot{border-color:var(--side2);box-shadow:0 0 10px var(--glow)}
.nav{gap:2px}
.nv{height:40px;font-size:14px;color:var(--text2);border-radius:14px;transition:color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring),background-color var(--d-hover) var(--e-out)}
.nv:hover{background:rgba(255,255,255,.04);color:#fff;transform:translateX(3px)}
.nv.on{color:#fff}
.nv.on .ic{color:var(--accent-hi);filter:drop-shadow(0 0 6px var(--glow))}
.pill-bg{background:linear-gradient(90deg,var(--accent-soft),rgba(255,255,255,.035));border:1px solid var(--accent-line);border-radius:14px;box-shadow:0 0 24px var(--glow-soft),inset 0 1px 0 rgba(255,255,255,.06);transition:top var(--d-page) var(--e-spring),height var(--d-card) var(--e-out)}
.pill-bg:before{content:"";position:absolute;left:-1px;top:8px;bottom:8px;width:3px;border-radius:3px;background:var(--accent);box-shadow:0 0 12px var(--glow),0 0 4px var(--accent)}
.nv .badge{background:var(--accent-soft);color:var(--accent-hi);box-shadow:inset 0 0 0 1px var(--accent-line)}
.nv.on .badge{background:var(--accent);color:var(--accent-text)}
.side .foot{color:var(--muted)}
.side .foot .lgt{margin:10px auto 0}
/* ---------- floating bottom bar (inspired by the reference: glass bar + lamp) ---------- */
.fnav{z-index:var(--z-nav)}
.fpill{background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.015)),var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  border-radius:26px;padding:6px 8px;gap:0;box-shadow:0 0 0 1px var(--line2),0 0 0 1.5px var(--accent-line),0 18px 40px rgba(0,0,0,.45),0 0 34px var(--glow-soft),inset 0 1px 0 rgba(255,255,255,.08);transition:box-shadow var(--d-card) var(--e-out)}
.fpill:hover{box-shadow:0 0 0 1px var(--line2),0 0 0 1.5px var(--accent),0 18px 40px rgba(0,0,0,.45),0 0 44px var(--glow),inset 0 1px 0 rgba(255,255,255,.1)}
.fpill .fbg{display:none}
.fpill button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;height:52px;min-width:66px;padding:0 10px;border-radius:18px;font-size:11.5px;font-weight:650;color:var(--muted);transition:color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.fpill button .ic{width:20px;height:20px;transition:transform var(--d-card) var(--e-spring),filter var(--d-hover) var(--e-out)}
.fpill button:hover{color:var(--text);transform:translateY(-1px)}
.fpill button:hover .ic{transform:translateY(-1px) scale(1.06)}
.fpill button.on{color:#fff}
.fpill button.on .ic{color:var(--accent-hi);filter:drop-shadow(0 0 8px var(--glow))}
.flamp{position:absolute;top:0;height:100%;pointer-events:none;z-index:0;transition:left var(--d-page) var(--e-spring),width var(--d-card) var(--e-out);opacity:0}
.flamp.on{opacity:1}
.flamp:before{content:"";position:absolute;left:28%;right:28%;top:-1px;height:3px;border-radius:0 0 3px 3px;background:var(--accent-hi);box-shadow:0 0 10px var(--accent),0 0 22px var(--glow)}
.flamp:after{content:"";position:absolute;left:8%;right:8%;top:2px;bottom:6px;clip-path:polygon(28% 0,72% 0,100% 100%,0 100%);background:linear-gradient(180deg,var(--glow),transparent 85%);opacity:.55;border-radius:0 0 14px 14px}
.fthumb{display:block;bottom:4px;height:2px;opacity:.85}
.fplus{background:linear-gradient(160deg,var(--accent),var(--accent2));box-shadow:0 12px 26px rgba(0,0,0,.4),0 0 24px var(--glow-soft)}
.fplus:hover{box-shadow:0 12px 26px rgba(0,0,0,.4),0 0 30px var(--glow)}
.fmore{display:none}
.main.hasdock .fpill button{min-width:54px;padding:0 6px;font-size:11px}
/* ---------- liquid glass theme control ---------- */
.lgt{position:relative;display:inline-flex;align-items:center;gap:2px;padding:4px;border-radius:999px;isolation:isolate;
  background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.02) 55%,rgba(255,255,255,.05)),rgba(74,222,139,.07);
  backdrop-filter:blur(14px) saturate(170%);-webkit-backdrop-filter:blur(14px) saturate(170%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.22),inset 0 -1px 0 rgba(0,0,0,.25),inset 0 0 0 1px rgba(255,255,255,.07),0 8px 22px rgba(0,0,0,.3),0 0 20px var(--glow-soft);
  transition:box-shadow var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.lgt:before{content:"";position:absolute;left:10%;right:10%;top:1px;height:45%;border-radius:999px;background:linear-gradient(180deg,rgba(255,255,255,.18),transparent);pointer-events:none;z-index:2}
.lgt:hover{box-shadow:inset 0 1px 0 rgba(255,255,255,.28),inset 0 -1px 0 rgba(0,0,0,.25),inset 0 0 0 1px var(--accent-line),0 10px 26px rgba(0,0,0,.32),0 0 30px var(--glow)}
.lgt button{position:relative;z-index:3;width:34px;height:30px;border-radius:999px;display:grid;place-items:center;transition:transform var(--d-card) var(--e-spring)}
.lgt button i{width:14px;height:14px;border-radius:50%;box-shadow:inset 0 1px 1px rgba(255,255,255,.4),0 0 0 1px rgba(0,0,0,.25);transition:transform var(--d-card) var(--e-spring),box-shadow var(--d-hover) var(--e-out)}
.lgt button:hover i{transform:scale(1.15)}
.lgt button:active{transform:scale(.88)}
.lgt button.on i{box-shadow:inset 0 1px 1px rgba(255,255,255,.5),0 0 0 1px rgba(255,255,255,.35),0 0 12px var(--glow)}
.lgt .drop{position:absolute;z-index:1;top:4px;bottom:4px;border-radius:999px;
  background:radial-gradient(120% 90% at 30% 15%,rgba(255,255,255,.34),rgba(255,255,255,.06) 45%,rgba(74,222,139,.12) 80%),rgba(74,222,139,.10);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.45),inset 0 -2px 4px rgba(0,0,0,.18),inset 0 0 0 1px rgba(255,255,255,.14),0 4px 14px rgba(0,0,0,.25),0 0 18px var(--glow);
  transition:left var(--d-page) var(--e-bounce),width var(--d-card) var(--e-out),transform var(--d-micro) var(--e-out)}
.lgt.press .drop{transform:scaleX(1.18) scaleY(.92)}
.lgt.big button{width:44px;height:38px}.lgt.big button i{width:18px;height:18px}
.lgt-lbl{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.lgt-lbl span{font-size:13px;color:var(--muted);font-weight:600}
/* theme switch: smooth colour crossfade */
html.theming *,html.theming *:before,html.theming *:after{transition:background-color 600ms var(--e-out),border-color 600ms var(--e-out),color 600ms var(--e-out),box-shadow 600ms var(--e-out)!important}
::view-transition-old(root),::view-transition-new(root){animation-duration:620ms;animation-timing-function:cubic-bezier(.22,1,.36,1)}
/* ---------- intro: logo, loading ring, press to enter ---------- */
#intro{position:fixed;inset:0;z-index:var(--z-intro);display:grid;place-items:center;background:radial-gradient(900px 600px at 50% 42%,var(--bg-glow),transparent 70%),var(--bg);transition:opacity 620ms var(--e-out)}
#intro.gone{opacity:0;pointer-events:none}
#intro .ib0{display:grid;justify-items:center;gap:22px}
#introLogo{position:relative;width:118px;height:118px;border-radius:34px;display:grid;place-items:center;cursor:default;-webkit-tap-highlight-color:transparent;
  background:linear-gradient(160deg,var(--card3),var(--side2));box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 0 0 1px var(--accent-line),0 20px 50px rgba(0,0,0,.5),0 0 60px var(--glow-soft);
  opacity:0;transform:scale(.72);filter:blur(6px);animation:logoin 1100ms var(--e-out) 120ms forwards;will-change:transform,opacity,filter;contain:layout}
#introLogo:after{content:"";position:absolute;inset:-1px;border-radius:inherit;box-shadow:0 0 0 1px var(--accent),0 0 80px var(--glow);opacity:0;pointer-events:none;will-change:opacity}
#intro.ready #introLogo:after{animation:breathe 2.8s var(--e-io) 1.2s infinite}
#introLogo svg.mk{width:62px;height:62px;filter:drop-shadow(0 0 14px var(--glow))}
#introLogo .lring{position:absolute;inset:-16px;width:calc(100% + 32px);height:calc(100% + 32px);transform:rotate(-90deg);overflow:visible}
#introLogo .lring circle{fill:none;stroke-width:2.5;stroke-linecap:round}
#introLogo .lring .tr{stroke:var(--line2)}
#introLogo .lring .pg{stroke:var(--accent);stroke-dasharray:1;stroke-dashoffset:.94;filter:drop-shadow(0 0 6px var(--glow));transition:stroke-dashoffset 700ms var(--e-out)}
#intro:not(.ready) .lring{animation:lspin 1.6s cubic-bezier(.5,.1,.5,.9) infinite;will-change:transform}
#intro.ready #introLogo{cursor:pointer;transition:transform var(--d-card) var(--e-spring)}
#intro.ready #introLogo:hover{transform:scale(1.04)}
#intro.ready #introLogo:active{transform:scale(.96)}
#intro .t1{font-size:15px;font-weight:800;letter-spacing:4px;color:var(--text);opacity:0;animation:fadeup 900ms var(--e-out) 420ms forwards}
#intro .t2{font-size:12px;font-weight:700;letter-spacing:2.2px;text-transform:uppercase;color:var(--muted);min-height:16px;opacity:0;animation:fadeup 900ms var(--e-out) 560ms forwards;transition:color var(--d-card) var(--e-out)}
#intro.ready .t2{color:var(--accent-hi)}
@keyframes logoin{to{opacity:1;transform:none;filter:none}}
@keyframes fadeup{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes lspin{to{transform:rotate(270deg)}}
@keyframes breathe{0%,100%{opacity:0}50%{opacity:1}}
.flyer{position:fixed;z-index:calc(var(--z-intro) + 1);pointer-events:none;transform-origin:0 0;will-change:transform}
.flyer .fl-in{position:absolute;inset:0}
.flyer .fl-sq,.flyer .fl-ci{position:absolute;inset:0;background:linear-gradient(160deg,var(--card3),var(--side2));box-shadow:0 0 0 1px var(--accent-line),0 20px 50px rgba(0,0,0,.5),0 0 60px var(--glow-soft);will-change:opacity}
.flyer .fl-sq{border-radius:28.8%}.flyer .fl-ci{border-radius:50%;opacity:0}
.flyer .fl-av{border-radius:50%;overflow:hidden}
.flyer .fl-glow{position:absolute;inset:-35%;border-radius:50%;background:radial-gradient(closest-side,rgba(74,222,139,.55),rgba(74,222,139,.18) 55%,transparent 72%);opacity:0;will-change:transform,opacity}
.flyer .fl-ring{position:absolute;inset:-2px;border-radius:50%;box-shadow:0 0 0 3px var(--accent-hi),0 0 24px var(--glow);opacity:0;will-change:transform,opacity}
.flyer .fl-logo,.flyer .fl-av{position:absolute;inset:0;display:grid;place-items:center;will-change:transform,opacity}
.flyer .fl-bl{filter:blur(8px)}.flyer .fl-logo.fl-bl{filter:blur(3px)}
/* the lens: a circle whose giant shadow is the cover. Growing it is a pure GPU scale, so the reveal stays smooth */
.lens{position:fixed;inset:0;z-index:calc(var(--z-login) - 1);pointer-events:none;will-change:transform;contain:strict}
.lens i,.lens b{position:absolute;border-radius:50%;will-change:opacity}
.lens i{box-shadow:0 0 22px 6px rgba(74,222,139,.38);opacity:0}.lens b{background:var(--bg)}
.flyer .fl-logo svg{width:52%;height:52%}
.flyer .fl-av{opacity:0;background:var(--av-bg) center/cover no-repeat;color:#fff;font-weight:800;font-size:40px}
.lg .mark svg{width:30px;height:30px}
/* ---------- avatars: real <img> on top of initials, so a broken file falls back cleanly ---------- */
.tav,.in-av,.hav{position:relative;overflow:hidden}
.tav>img,.in-av>img,.hav>img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:inherit}
.idc .ring .in-av,.pav .tav{background:var(--av-bg)}
/* ---------- badges ---------- */
.bdg{display:inline-flex;gap:4px;align-items:center;flex-wrap:wrap;vertical-align:middle}
.badge-i{--h1:#7BEBAE;--h2:#2FBF71;position:relative;width:22px;height:22px;border-radius:8px;display:inline-grid;place-items:center;flex:none;overflow:hidden;
  background:linear-gradient(150deg,color-mix(in srgb,var(--h1) 30%,transparent),color-mix(in srgb,var(--h2) 14%,transparent));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.18),0 0 0 1px color-mix(in srgb,var(--h1) 45%,transparent),0 0 12px color-mix(in srgb,var(--h1) 22%,transparent);
  color:var(--h1);transition:transform var(--d-card) var(--e-spring),box-shadow var(--d-hover) var(--e-out)}
.badge-i .ic{width:13px;height:13px}
.badge-i:after{content:"";position:absolute;top:-50%;left:-80%;width:50%;height:200%;transform:rotate(25deg);background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);transition:left 700ms var(--e-out)}
.badge-i:hover{transform:translateY(-2px) scale(1.12)}.badge-i:hover:after{left:140%}
.badge-i.lg{width:auto;height:30px;border-radius:11px;padding:0 10px 0 8px;gap:6px;font-size:12px;font-weight:700;display:inline-flex}
.badge-i.lg .ic{width:15px;height:15px}
.b-top_caller{--h1:#7BEBAE;--h2:#2FBF71}.b-meetings{--h1:#9ADCF0;--h2:#3BA3C4}.b-revenue{--h1:#EBCF7D;--h2:#B98F2E}.b-consistency{--h1:#B7E6A0;--h2:#6AAE4A}
.b-rising{--h1:#A4F0D8;--h2:#33B99A}.b-closer{--h1:#C9E89A;--h2:#86B23F}.b-century{--h1:#F0B98C;--h2:#C6743C}.b-mvp{--h1:#F2D88C;--h2:#D2A23C}
.bdg-list{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:14px}
/* ---------- leaderboard ---------- */
.lbd{display:grid;gap:18px;padding-bottom:110px}
.lb-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.lseg{position:relative;display:inline-flex;padding:5px;border-radius:999px;background:var(--panel);border:1px solid var(--line);box-shadow:inset 0 2px 6px rgba(0,0,0,.25)}
.lseg button{white-space:nowrap;position:relative;z-index:1;height:38px;padding:0 18px;border-radius:999px;font-weight:700;font-size:13.5px;color:var(--muted);display:inline-flex;align-items:center;gap:7px;transition:color var(--d-hover) var(--e-out)}
.lseg button .ic{width:16px;height:16px}
.lseg button.on{color:var(--text)}
.lseg .sk{position:absolute;top:5px;bottom:5px;border-radius:999px;background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.02)),var(--accent-soft);box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 0 0 1px var(--accent-line),0 0 20px var(--glow-soft);transition:left var(--d-page) var(--e-spring),width var(--d-card) var(--e-out)}
.lseg.sm button{height:32px;padding:0 13px;font-size:12.5px}
.lseg .lbs{display:none}
@media (max-width:860px){.lseg .lbs{display:inline}}
.pods{display:grid;grid-template-columns:1fr 1.12fr 1fr;align-items:end;gap:16px;max-width:880px;margin:6px auto 0;width:100%}
.pod{position:relative;text-align:center;padding:20px 14px 18px;border-radius:26px;cursor:pointer;background:linear-gradient(180deg,var(--card2),var(--card-end));border:1px solid var(--line);box-shadow:var(--sh),var(--hi);transition:transform var(--d-card) var(--e-spring),box-shadow var(--d-card) var(--e-out)}
.pod:hover{transform:translateY(-4px)}
.pod .rk{position:absolute;top:12px;left:14px;font-size:12px;font-weight:800;color:var(--muted)}
.pod .crown{position:absolute;top:-16px;left:50%;transform:translateX(-50%);width:34px;height:34px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(160deg,rgba(242,216,140,.3),rgba(210,162,60,.15));color:#F2D88C;box-shadow:0 0 0 1px rgba(242,216,140,.45),0 0 22px rgba(242,216,140,.3)}
.pod .crown .ic{width:18px;height:18px}
.pod .tav{width:72px;height:72px;margin:6px auto 0;font-size:24px;box-shadow:0 0 0 3px var(--pc,var(--line2)),0 0 26px var(--pg,transparent)}
.pod.p1{padding-top:30px;background:linear-gradient(180deg,var(--card3),var(--card-end));box-shadow:var(--sh),0 0 0 1px var(--accent-line),0 0 50px var(--glow-soft),var(--hi);--pc:#E8CD7E;--pg:rgba(232,205,126,.35)}
.pod.p1 .tav{width:92px;height:92px;font-size:30px}
.pod.p2{--pc:#C9D6CF;--pg:rgba(201,214,207,.2)}.pod.p3{--pc:#D7A47C;--pg:rgba(215,164,124,.2)}
.pod h4{margin-top:12px;font-size:15.5px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pod .v{font-size:26px;font-weight:800;letter-spacing:-.5px;margin-top:4px;font-variant-numeric:tabular-nums}
.pod.p1 .v{font-size:32px;color:var(--accent-hi);text-shadow:0 0 22px var(--glow)}
.pod .u{font-size:12px;color:var(--muted);font-weight:600}
.pod .bdg{justify-content:center;margin-top:10px;min-height:22px}
.pod .base{height:8px;border-radius:4px;margin:14px auto 0;width:60%;background:linear-gradient(90deg,transparent,var(--pc),transparent);opacity:.5}
.lbl{display:grid;gap:8px}
.lbr{display:grid;grid-template-columns:34px 44px minmax(0,1fr) minmax(80px,1.1fr) auto;align-items:center;gap:12px;padding:10px 16px;border-radius:20px;cursor:pointer;background:linear-gradient(180deg,var(--card),var(--card-end));border:1px solid var(--line);transition:transform var(--d-card) var(--e-spring),box-shadow var(--d-card) var(--e-out),background-color var(--d-hover) var(--e-out)}
.lbr:hover{transform:translateX(4px);box-shadow:0 0 0 1px var(--accent-line),0 0 24px var(--glow-soft)}
.lbr.me{box-shadow:0 0 0 1px var(--accent-line)}
.lbr .rk{font-weight:800;color:var(--muted);text-align:center;font-variant-numeric:tabular-nums}
.lbr .tav{width:40px;height:40px}
.lbr .nm b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lbr .nm .bdg{margin-top:3px}
.lbr .lbar{height:8px;border-radius:4px;background:rgba(255,255,255,.05);overflow:hidden}
.lbr .lbar i{display:block;height:100%;width:0;border-radius:4px;background:linear-gradient(90deg,var(--accent2),var(--accent-hi));box-shadow:0 0 12px var(--glow);transition:width 900ms var(--e-out)}
.lbr .v{font-weight:800;font-size:16px;font-variant-numeric:tabular-nums;text-align:right;min-width:70px}
.lb-note{font-size:12.5px;color:var(--muted);text-align:center}
.lb-badges{padding:18px 20px}
.lb-badges .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin-top:12px}
.lb-badges .bi{display:flex;gap:10px;align-items:center;padding:10px 12px;border-radius:16px;background:rgba(0,0,0,.18);border:1px solid var(--line)}
.lb-badges .bi b{display:block;font-size:13.5px}.lb-badges .bi small{display:block;color:var(--muted);font-size:12px;line-height:1.35}
.lb-badges .bi .who{display:flex;gap:-6px;margin-left:auto}.lb-badges .bi .who .tav{width:24px;height:24px;font-size:9px;margin-left:-6px;box-shadow:0 0 0 2px var(--card)}
/* ---------- announcements ---------- */
.ps{display:grid;gap:16px;padding-bottom:110px;max-width:900px;margin:0 auto;width:100%}
.ps-comp{padding:16px 18px}
.ps-comp .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.ps-comp .inp{width:100%}
.ps-comp textarea.inp{min-height:84px;margin-top:10px}
.ps-comp .more{display:grid;grid-template-rows:0fr;transition:grid-template-rows var(--d-card) var(--e-out)}
.ps-comp.open .more{grid-template-rows:1fr}.ps-comp .more>div{overflow:hidden}
.ps-comp .acts{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap}
.ps-f{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.post{padding:18px 20px;transition:transform var(--d-card) var(--e-spring),box-shadow var(--d-card) var(--e-out)}
.post.pinned{box-shadow:var(--sh),0 0 0 1px var(--accent-line),0 0 34px var(--glow-soft)}
.post .ph2{display:flex;align-items:center;gap:12px}
.post .au{display:flex;align-items:center;gap:10px;min-width:0;cursor:pointer;border-radius:14px;padding:2px 6px 2px 2px;margin:-2px;transition:background-color var(--d-hover) var(--e-out)}
.post .au:hover{background:rgba(255,255,255,.04)}
.post .au .tav{width:40px;height:40px}
.post .au b{display:flex;align-items:center;gap:6px;font-size:14.5px}
.post .au small{display:block;color:var(--muted);font-size:12px;margin-top:1px}
.post .kd{margin-left:auto;display:flex;gap:6px;align-items:center;flex:none}
.ptag{height:24px;padding:0 10px;border-radius:12px;font-size:11.5px;font-weight:800;letter-spacing:.3px;display:inline-flex;align-items:center;gap:5px;background:var(--accent-soft);color:var(--accent-hi);box-shadow:inset 0 0 0 1px var(--accent-line)}
.ptag.idea{background:rgba(233,193,90,.12);color:#EDCB74;box-shadow:inset 0 0 0 1px rgba(233,193,90,.3)}
.ptag.update{background:rgba(143,199,240,.12);color:#A9D4F3;box-shadow:inset 0 0 0 1px rgba(143,199,240,.3)}
.ptag .ic{width:12px;height:12px}
.post h3{font-size:18px;font-weight:800;margin:14px 0 6px;letter-spacing:-.2px;word-break:break-word}
.post .bd{white-space:pre-wrap;word-break:break-word;color:var(--text2);line-height:1.55;font-size:14px}
.post .ed{font-size:11.5px;color:var(--faint);margin-top:8px}
.post .rx{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:14px}
.post .rx button{height:32px;min-width:44px;padding:0 10px;border-radius:16px;background:rgba(0,0,0,.18);border:1px solid var(--line);font-size:13px;font-weight:700;color:var(--muted);display:inline-flex;align-items:center;gap:6px;transition:transform var(--d-card) var(--e-spring),background-color var(--d-hover) var(--e-out),border-color var(--d-hover) var(--e-out)}
.post .rx button:hover{transform:translateY(-2px);border-color:var(--line2)}
.post .rx button.on{background:var(--accent-soft);border-color:var(--accent-line);color:var(--accent-hi);box-shadow:0 0 14px var(--glow-soft)}
.post .rx button.pulse{animation:rxp 420ms var(--e-bounce)}
@keyframes rxp{40%{transform:scale(1.22)}}
.post .rx .cm{margin-left:auto}
.post .cms{display:grid;grid-template-rows:0fr;transition:grid-template-rows var(--d-card) var(--e-out)}
.post.cmo .cms{grid-template-rows:1fr}.post .cms>div{overflow:hidden}
.cmt{display:flex;gap:10px;padding:10px 0 0}
.cmt .tav{width:30px;height:30px;font-size:11px}
.cmt .cb{flex:1;min-width:0;background:rgba(0,0,0,.16);border-radius:14px;padding:8px 12px;border:1px solid var(--line)}
.cmt .cb b{font-size:12.5px}.cmt .cb small{color:var(--faint);font-size:11.5px;margin-left:6px}
.cmt .cb p{font-size:13.5px;white-space:pre-wrap;word-break:break-word;margin-top:2px;color:var(--text2)}
.cmt .cx{opacity:0;transition:opacity var(--d-hover) var(--e-out)}.cmt:hover .cx{opacity:1}
.cadd{display:flex;gap:8px;margin-top:10px}.cadd .inp{flex:1;min-width:0}
.pmenu{position:relative}
.pmenu .mn{position:absolute;right:0;top:38px;z-index:5;min-width:160px;padding:6px;border-radius:16px;background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border:1px solid var(--line2);box-shadow:var(--sh-lg);opacity:0;transform:translateY(-6px) scale(.96);transform-origin:top right;pointer-events:none;transition:opacity var(--d-pop) var(--e-out),transform var(--d-pop) var(--e-spring)}
.pmenu.on .mn{opacity:1;transform:none;pointer-events:auto}
.pmenu .mn button{display:flex;width:100%;align-items:center;gap:10px;padding:9px 10px;border-radius:11px;font-size:13.5px;font-weight:600;text-align:left;transition:background-color var(--d-hover) var(--e-out)}
.pmenu .mn button:hover{background:rgba(255,255,255,.06)}.pmenu .mn button.dn{color:var(--bad)}
.pmenu .mn .ic{width:16px;height:16px}
/* hover profile card */
.hcard{position:fixed;z-index:calc(var(--z-modal) - 1);width:300px;border-radius:24px;overflow:hidden;pointer-events:auto;
  background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border:1px solid var(--line2);
  box-shadow:var(--sh-lg),0 0 40px var(--glow-soft),inset 0 1px 0 rgba(255,255,255,.08);
  opacity:0;transform:translateY(8px) scale(.96);transition:opacity var(--d-pop) var(--e-out),transform var(--d-card) var(--e-spring)}
.hcard.on{opacity:1;transform:none}
.hcard .hb{height:76px;background:linear-gradient(120deg,var(--side1),var(--main2)) center/cover no-repeat}
.hcard .hm{padding:0 16px 16px;margin-top:-30px;position:relative}
.hcard .tav{width:60px;height:60px;font-size:20px;box-shadow:0 0 0 3px var(--card),0 0 20px var(--glow-soft)}
.hcard h4{font-size:16px;font-weight:800;margin-top:8px;display:flex;align-items:center;gap:6px}
.hcard .sub{color:var(--muted);font-size:12.5px;margin-top:1px}
.hcard p{font-size:13px;color:var(--text2);margin-top:8px;line-height:1.45;max-height:58px;overflow:hidden}
.hcard .hs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}
.hcard .hs div{background:rgba(0,0,0,.2);border-radius:12px;padding:7px 4px;text-align:center}.hcard .hs b{display:block;font-size:15px}.hcard .hs span{font-size:11px;color:var(--muted);font-weight:600}
.hcard .bdg{margin-top:10px}
/* migration / info notes */
.need{padding:22px 24px}.need h3{font-size:17px}.need p{color:var(--text2);margin-top:6px;line-height:1.5;font-size:13.5px}
.need code{background:rgba(0,0,0,.3);padding:1px 6px;border-radius:6px;font-size:12px}
/* ---------- media editor + lead generation + switches ---------- */
.mprev{display:grid;justify-items:center;gap:12px;margin-top:12px}
.mprev .pv-av{width:150px;height:150px;border-radius:50%;overflow:hidden;background:var(--av-bg);box-shadow:0 0 0 3px var(--accent-line),0 0 30px var(--glow-soft)}
.mprev .pv-bn{width:100%;aspect-ratio:4/1;border-radius:18px;overflow:hidden;background:var(--av-bg);box-shadow:0 0 0 1px var(--line2)}
.mprev img{width:100%;height:100%;object-fit:cover;display:block}
.mprev .meta{font-size:12.5px;color:var(--muted)}
.rng{width:100%;accent-color:var(--accent)}
.pban{background-position:center var(--bp,50%)}
.pban.has-img{position:relative;overflow:hidden}.pban>img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center var(--bp,50%)}
.tgl{position:relative;width:50px;height:30px;border-radius:15px;flex:none;background:rgba(255,255,255,.08);box-shadow:inset 0 0 0 1px var(--line2),inset 0 2px 5px rgba(0,0,0,.3);transition:background-color var(--d-card) var(--e-out),box-shadow var(--d-card) var(--e-out)}
.tgl:after{content:"";position:absolute;left:3px;top:3px;width:24px;height:24px;border-radius:50%;background:linear-gradient(180deg,#fff,#D8E6DD);box-shadow:0 2px 6px rgba(0,0,0,.35);transition:transform var(--d-card) var(--e-spring)}
.tgl.on{background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent-line),0 0 18px var(--glow-soft)}
.tgl.on:after{transform:translateX(20px);background:linear-gradient(180deg,var(--accent-hi),var(--accent))}
.lgen .row{display:flex;align-items:center;gap:14px;justify-content:space-between}
.lgen .stt{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;font-weight:700;padding:6px 12px;border-radius:12px;background:rgba(0,0,0,.2);color:var(--muted);margin-top:12px}
.lgen .stt i{width:8px;height:8px;border-radius:50%;background:var(--faint)}
.lgen .stt.on i{background:var(--warn);box-shadow:0 0 10px rgba(233,193,90,.6)}
.lgen .prov{display:grid;gap:8px;margin-top:12px}
.lgen .prov label{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:14px;background:rgba(0,0,0,.16);border:1px solid var(--line);cursor:pointer;transition:border-color var(--d-hover) var(--e-out)}
.lgen .prov label:hover{border-color:var(--line2)}.lgen .prov input{margin-top:3px;accent-color:var(--accent)}
.lgen .prov b{font-size:13.5px}.lgen .prov small{display:block;color:var(--muted);font-size:12px;line-height:1.4;margin-top:2px}
.lgen-card{padding:16px 18px;margin-bottom:14px;display:flex;gap:14px;align-items:center}
/* ---------- one bar chart style for the whole app (plain HTML, no overlaps) ---------- */
.bch{display:grid;grid-template-columns:auto repeat(var(--n),minmax(0,1fr));gap:0 8px;padding-top:24px;overflow:clip;overflow-clip-margin:0}
.bch .ax{display:flex;flex-direction:column;justify-content:space-between;font-size:11.5px;color:var(--faint);text-align:right;padding:0 2px 30px 0;font-variant-numeric:tabular-nums;min-width:22px}
.bch .ax span{transform:translateY(-50%)}.bch .ax span:last-child{transform:translateY(50%)}
.bch .dcol{position:relative;display:grid;grid-template-rows:1fr 30px;min-width:0}
.bch .plot{position:relative;display:flex;align-items:flex-end;justify-content:center;gap:4px;border-bottom:1px solid var(--line2);background:linear-gradient(var(--line),var(--line)) 0 0/100% 1px no-repeat,linear-gradient(var(--line),var(--line)) 0 50%/100% 1px no-repeat}
.bch .b{position:relative;width:min(24px,42%);border-radius:8px 8px 3px 3px;transform-origin:50% 100%;transform:scaleY(0);transition:transform 900ms var(--e-spring),filter var(--d-hover) var(--e-out);transition-delay:calc(var(--i)*55ms + 200ms)}
.bch .b0{background:linear-gradient(180deg,var(--accent-hi),var(--accent2));box-shadow:0 0 16px var(--glow-soft)}
.bch .b1{width:min(12px,24%);background:linear-gradient(180deg,#F2D88C,#C9A03F);box-shadow:0 0 12px rgba(233,193,90,.22)}
.bch .fut .b0{background:linear-gradient(180deg,rgba(154,242,194,.55),rgba(47,191,113,.35));box-shadow:none;outline:1px dashed var(--accent-line);outline-offset:-1px}
.in .bch .b,.bch.in .b{transform:scaleY(1)}
.bch .b>span{position:absolute;bottom:calc(100% + 4px);left:50%;transform:translateX(-50%);font-size:11.5px;font-weight:800;white-space:nowrap}
.bch .b1>span{color:#EDCB74;font-size:10.5px}
.bch .dl{display:grid;place-items:center;font-size:12px;font-weight:700;color:var(--muted)}
.bch .dcol.td .dl{color:var(--accent-hi)}
.bch .dcol:hover .b{filter:brightness(1.12)}
.bch .tip{position:absolute;bottom:40px;left:50%;transform:translate(-50%,6px);white-space:nowrap;padding:6px 10px;border-radius:10px;background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border:1px solid var(--line2);font-size:12px;font-weight:600;opacity:0;pointer-events:none;transition:opacity var(--d-pop) var(--e-out),transform var(--d-pop) var(--e-out);z-index:3}
.bch .dcol:hover .tip{opacity:1;transform:translate(-50%,0)}
.bch .dcol:nth-child(2) .tip{left:0;transform:translate(0,6px)}.bch .dcol:nth-child(2):hover .tip{transform:none}
.bch .dcol:nth-last-child(-n+2) .tip{left:auto;right:0;transform:translate(0,6px)}.bch .dcol:nth-last-child(-n+2):hover .tip{transform:none}
/* mobile header avatar + "more" sheet (hidden on desktop) */
.mav{display:none}
.sheet{position:fixed;inset:0;z-index:var(--z-modal);display:none}
.sheet.on{display:block}
.sheet .sbk{position:absolute;inset:0;background:rgba(4,10,7,.5);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);opacity:0;transition:opacity var(--d-pop) var(--e-out)}
.sheet .sp{position:absolute;left:8px;right:8px;bottom:calc(8px + env(safe-area-inset-bottom));padding:10px 14px 16px;border-radius:30px;background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border:1px solid var(--line2);box-shadow:var(--sh-lg),0 0 40px var(--glow-soft);transform:translateY(110%);transition:transform var(--d-page) var(--e-spring)}
.sheet.show .sbk{opacity:1}.sheet.show .sp{transform:none}
.sheet .grab{width:42px;height:5px;border-radius:3px;background:var(--line2);margin:2px auto 12px}
.sheet .sg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.sheet .sg button{display:grid;justify-items:center;gap:8px;padding:14px 6px;border-radius:20px;background:rgba(255,255,255,.035);border:1px solid var(--line);font-size:12.5px;font-weight:700;color:var(--text2);transition:transform var(--d-card) var(--e-spring),background-color var(--d-hover) var(--e-out),border-color var(--d-hover) var(--e-out)}
.sheet .sg button .ic{width:24px;height:24px;color:var(--accent-hi)}
.sheet .sg button.on{background:var(--accent-soft);border-color:var(--accent-line);color:#fff}
.sheet .sg button:active{transform:scale(.94)}
.sheet .sx{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,1fr);align-items:center;gap:10px;margin-top:14px;padding:12px 2px 0;border-top:1px solid var(--line)}
.sheet .sx .btn{height:40px;padding:0 10px;white-space:nowrap;min-width:0}
.sheet .nb{position:absolute;top:8px;right:16px;min-width:18px;height:18px;border-radius:9px;background:var(--accent);color:var(--accent-text);font-size:10.5px;font-weight:800;display:grid;place-items:center;padding:0 5px}
.sheet .sg button{position:relative}
.sheet .sg .sht{display:none}
.ndot{position:absolute;top:8px;right:calc(50% - 18px);width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--glow);opacity:0;transform:scale(0);transition:transform var(--d-card) var(--e-bounce),opacity var(--d-pop)}
.ndot.on{opacity:1;transform:none}

/* =====================================================================
   PHONE & TABLET — a layout of its own, not the desktop squeezed down
   ===================================================================== */
@media (max-width:860px){
  body{font-size:15px}
  .main{background:linear-gradient(180deg,var(--main1),var(--bg) 60%);box-shadow:none}
  .top{padding:12px 18px 8px;gap:10px;min-height:64px}
  .mav{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;padding:2px;flex:none;background:conic-gradient(from 200deg,var(--accent),var(--accent-hi),var(--accent));box-shadow:0 0 16px var(--glow-soft)}
  .mav .in-av{width:100%;height:100%;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:14px;background:var(--av-bg);color:#fff}
  .top h1{font-size:21px;letter-spacing:-.3px}
  .top .lgt,#bellBtn{display:none}
  #outBtn{display:none}
  .rb{width:42px;height:42px}
  .sync{height:36px;padding:0 12px;font-size:12px}.sync span{display:none}.sync{width:36px;padding:0;justify-content:center}
  body.p-find .srch,body.p-called .srch{display:block}
  .srch{order:9;flex:1 1 100%;max-width:none;margin:2px 0 0}
  .top{flex-wrap:wrap}
  .srch input{height:44px}
  .page{padding:10px 16px calc(120px + env(safe-area-inset-bottom))}
  .card{border-radius:24px}
  /* bottom tab bar */
  .fnav{left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom));padding:0;background:none;backdrop-filter:none;-webkit-backdrop-filter:none;box-shadow:none;transform:none}
  .fpill{width:100%;overflow:visible;justify-content:space-around;padding:6px 6px;border-radius:28px}
  .fpill button{flex:1 1 0;min-width:0;height:56px;padding:0 2px;font-size:11px}
  .fpill button.fx{display:none}
  .fmore{display:flex}
  .fplus{display:none}
  /* dashboard */
  .banner{grid-template-columns:minmax(0,1fr);padding:20px;border-radius:26px;gap:16px}
  .banner h2{font-size:22px}
  .banner .btn.pri{width:100%}
  .mtile{max-width:none}
  .stats{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;margin:16px 0}
  .stat{padding:14px 15px;border-radius:22px}
  .stat .spark{width:64px;height:28px;right:12px;top:16px}
  .stat .vl{font-size:26px}
  .chart-c,.types{padding:16px}
  .bch{gap:0 4px}.bch .b>span{font-size:10.5px}
  .legend{gap:10px;flex-wrap:wrap}
  .chart-c .hd{flex-wrap:wrap;gap:6px}
  /* called leads: swipeable columns, comfortable cards */
  .cstats{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}
  .cstat{padding:12px;border-radius:20px}.cstat .n{font-size:21px}
  .board{grid-template-columns:repeat(4,min(86vw,340px));gap:12px;margin:0 -16px;padding:0 16px 10px;scroll-padding:16px;overflow-x:auto;scroll-snap-type:x mandatory;overscroll-behavior-x:contain}
  .kc{padding:14px 15px;border-radius:20px}
  .kc b{font-size:15px}
  /* find leads */
  .fcard{padding:14px}
  .tools{gap:8px}.tools select{flex:1 1 140px}
  .li{padding:13px 12px}
  /* team */
  .tm-tiles{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}
  .tm-tile{padding:14px 15px}.tm-tile b{font-size:24px}
  .tm-p{padding:16px}
  .tm-p .nums{grid-template-columns:repeat(3,minmax(0,1fr))}
  /* leaderboard */
  .lb-head{display:grid;gap:10px;justify-content:stretch}
  .lseg{display:flex;width:100%}.lseg button{flex:1;justify-content:center;padding:0 6px;font-size:12.5px}
  .lseg button .lbx{display:none}
  .pods{grid-template-columns:minmax(0,1fr) minmax(0,1.15fr) minmax(0,1fr);gap:8px}
  .pod{padding:16px 6px 12px;border-radius:22px}.pod.p1{padding-top:26px}
  .pod .tav{width:52px;height:52px;font-size:17px}.pod.p1 .tav{width:66px;height:66px;font-size:22px}
  .pod h4{font-size:13px}.pod .v{font-size:18px}.pod.p1 .v{font-size:22px}
  .pod .bdg .badge-i:nth-child(n+3){display:none}
  .lbr{grid-template-columns:26px 40px minmax(0,1fr) auto;padding:10px 12px;gap:10px}
  .lbr .lbar{display:none}
  .lb-badges .grid{grid-template-columns:minmax(0,1fr)}
  /* announcements */
  .post{padding:16px}
  .post .ph2{flex-wrap:wrap}
  .post .kd{margin-left:auto}
  .ps-comp .acts .btn.pri{flex:1}
  .hcard{left:12px!important;right:12px;width:auto;top:auto!important;bottom:calc(92px + env(safe-area-inset-bottom))}
  /* profits / tables become cards */
  .dealtab{overflow:visible}
  .dr.h{display:none}
  .dr{grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;padding:14px 16px;border-top:1px solid var(--line)}
  .dr>div:nth-child(2){grid-column:1/-1;order:3;color:var(--muted);font-size:13px}
  .dr>div:nth-child(3),.dr>div:nth-child(5){display:none}
  .dr>div:nth-child(4){text-align:right}
  .dr>div:nth-child(6){grid-column:1/2;order:4;font-size:13px}
  .dr>div:nth-child(7){order:5;justify-self:end}
  /* dialogs become bottom sheets */
  .ov{place-items:end center}
  .dlg{width:100%;max-width:none;border-radius:28px 28px 0 0;padding:22px 18px calc(22px + env(safe-area-inset-bottom));max-height:88dvh;transform:translateY(100%)}
  .ov.on .dlg{transform:none}
  .btn{height:44px}.btn.sm{height:38px}
  .chip{height:38px}
  .ib{width:38px;height:38px}
  .toast{left:14px;right:14px;max-width:none;bottom:calc(96px + env(safe-area-inset-bottom))}
  .bell{left:12px;right:12px;width:auto;top:72px}
}
/* ---------- phone audit (11.3): no zoom-on-tap, bigger tap targets, nothing running off the screen ---------- */
.tocf{padding:18px 20px}
@media (max-width:860px){
  /* iPhone zooms the whole page into any text box under 16px; keep every field at 16px */
  input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=file]),select,textarea,.inp,.tools select,.cflt select{font-size:16px!important}
  .tools select{height:42px}
  .cmw{display:none}
  .fact .inp{height:42px}
  /* tap targets: at least ~38px tall */
  .mchip{height:38px;padding:0 14px;font-size:13px;border-radius:19px}
  .addm{height:40px;border-radius:20px;font-size:13.5px}
  .ch .fall{width:38px;height:38px;border-radius:12px}
  button.grp{min-height:42px}
  .cfm{height:38px;padding:0 14px;border-radius:19px}
  .nt-chips .chip{height:38px;padding:0 14px}
  .lseg button{min-height:40px}
  .cl-sum button{min-height:40px}
  .post .rx button{height:38px;min-width:48px;border-radius:19px}
  .sw{gap:12px;flex-wrap:wrap}.sw button{width:38px;height:38px}
  .evc{gap:10px}.evc button{width:38px;height:38px}
  .chk{width:28px;height:28px;position:relative}.chk:after{content:"";position:absolute;inset:-9px}
  /* lead pop-up: the owner box gets a full row, results become a 2 x 2 grid */
  .facts{gap:10px}
  .fact:has(#mOwner),.fact:has(#dOwner),.fact:has(#mOwner)+.fact,.fact:has(#dOwner)+.fact{grid-column:1/-1}
  .sb{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.sb .st{height:48px}
  /* Find Leads: city gets a full row like business type */
  .frow>div:nth-child(3){grid-column:1/3}
  /* Settings: Save button above the data-folder path, path wraps instead of running off */
  #aSave{flex:none}#aSave+.note,#dbNote{min-width:0;flex:1 1 100%;overflow-wrap:anywhere;word-break:break-all}
  #aSave{width:100%}
  div:has(>#aSave){flex-wrap:wrap;gap:10px!important}
  /* Call log: filters in two columns so the calls show up sooner */
  .cl-f{gap:10px 10px}
  .cl-f>div{flex:1 1 calc(50% - 5px);min-width:0}
  .cl-f>div:has(#clQ){flex:1 1 100%!important}
  .cl-f .inp,.cl-f select{min-width:0!important;width:100%}
  #clRange{flex:1 1 100%!important;display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}#clRange .chip{justify-content:center;padding:0 6px}
  #clLog{flex:1 1 100%;justify-content:center}
  /* Profits: payment rows wrap cleanly */
  .tocf .hd .pill{margin-left:auto}
  .prow{gap:10px}.prow>div:first-child{min-width:0}
  .prow .sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
}
@media (max-width:380px){
  .sheet .sx .btn{padding:0 8px;font-size:13px;gap:5px}
  .sheet .sx .btn .ic{width:16px;height:16px}
  .sheet .sg button{font-size:11.5px;padding:12px 3px;min-width:0}.sheet .sg .lgl{display:none}.sheet .sg .sht{display:inline}
  .cal-nav{width:100%;min-width:0;gap:6px}.cal-title{flex:1;min-width:0;font-size:16.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cal-nav .chip{padding:0 12px;flex:none}
  .cfm{padding:0 11px}
  .prow .num{font-size:13px}
}
@media (max-width:380px){
  .page{padding-left:12px;padding-right:12px}
  .fpill button{font-size:10.5px}
  .stats{gap:8px}.stat .spark{display:none}
  .pods{gap:6px}.pod .v{font-size:16px}.pod.p1 .v{font-size:19px}
  .sheet .sg{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
}
@media (min-width:600px) and (max-width:860px){
  .tm-people,.lb-badges .grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
  .stats{grid-template-columns:repeat(4,minmax(0,1fr))}
  .page{padding-left:24px;padding-right:24px}
  .fnav{left:50%;right:auto;transform:translateX(-50%);width:min(560px,94vw)}
}
@media (prefers-reduced-motion:reduce){
  #intro,#introLogo,#intro .t1,#intro .t2{animation:none!important;opacity:1!important;transform:none!important;filter:none!important}
  .bch .b{transform:none!important}
}

/* ---------- @mentions ---------- */
.ment{display:inline;padding:1px 6px;border-radius:7px;font-weight:700;color:var(--accent-hi);background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent-line);cursor:pointer;transition:background-color var(--d-hover) var(--e-out),box-shadow var(--d-hover) var(--e-out)}
.ment:hover{background:rgba(74,222,139,.22);box-shadow:inset 0 0 0 1px var(--accent),0 0 14px var(--glow-soft)}
.ment.me{color:#F2D88C;background:rgba(233,193,90,.14);box-shadow:inset 0 0 0 1px rgba(233,193,90,.4)}
.mpick{position:fixed;z-index:calc(var(--z-modal) + 5);min-width:220px;max-width:300px;padding:6px;border-radius:16px;background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border:1px solid var(--line2);box-shadow:var(--sh-lg),0 0 30px var(--glow-soft);animation:mpin var(--d-pop) var(--e-out)}
@keyframes mpin{from{opacity:0;transform:translateY(-4px) scale(.98)}}
.mpick button{display:flex;align-items:center;gap:10px;width:100%;padding:7px 9px;border-radius:11px;font-size:13.5px;font-weight:650;text-align:left;transition:background-color var(--d-hover) var(--e-out)}
.mpick button .tav{width:26px;height:26px;font-size:10px}
.mpick button small{margin-left:auto;color:var(--muted);font-size:11.5px}
.mpick button.on,.mpick button:hover{background:var(--accent-soft)}
</style>
</head>
<body>
<div id="intro" role="dialog" aria-label="Leafline is loading"><div class="ib0">
  <div id="introLogo" role="button" tabindex="-1" aria-label="Enter Leafline" aria-disabled="true"><svg class="mk" viewBox="0 0 64 64" aria-hidden="true"><defs><linearGradient id="lgA" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B8F7D4"/><stop offset=".55" stop-color="#4ADE8B"/><stop offset="1" stop-color="#1F9E5B"/></linearGradient></defs><path d="M51 9C30 9 13 20 13 39c0 6 2 11 5 15 2-12 9-22 21-29-9 8-15 18-17 30 4 2 8 3 12 3 19 0 26-19 26-37 0-5-1-9-9-12z" fill="url(#lgA)"/><path d="M22 55c3-13 10-23 21-30" fill="none" stroke="rgba(4,33,15,.45)" stroke-width="2.2" stroke-linecap="round"/></svg><svg class="lring" viewBox="0 0 100 100" aria-hidden="true"><circle class="tr" cx="50" cy="50" r="48"/><circle class="pg" id="introPg" cx="50" cy="50" r="48" pathLength="1"/></svg></div>
  <div class="t1">LEAFLINE</div><div class="t2" id="introTx" aria-live="polite">Loading</div></div></div>
<div class="app">
  <aside class="side" id="side">
    <div class="ring pop" id="ringBtn" title="Open account" role="button" tabindex="0"><div class="in-av" id="sideAv">LF</div><span class="dot"></span></div>
    <div class="hi pop" id="hiTxt">Hi there!</div>
    <nav class="nav pop" id="nav" aria-label="Main">
      <div class="pill-bg" id="navPill"></div>
      <button class="nv" data-go="dash"><i class="ic" data-ic="home"></i>Dashboard</button>
      <button class="nv" data-go="team"><i class="ic" data-ic="users"></i>Team</button>
      <button class="nv" data-go="board"><i class="ic" data-ic="trophy"></i>Leaderboard</button>
      <button class="nv" data-go="posts"><i class="ic" data-ic="mega"></i>Announcements<span class="badge" id="postsBadge" style="display:none">0</span></button>
      <button class="nv" data-go="msgs"><i class="ic" data-ic="chat"></i>Messages<span class="badge" id="msgBadge" style="display:none">0</span></button>
      <button class="nv" data-go="find"><i class="ic" data-ic="search"></i>Find Leads</button>
      <button class="nv" data-go="called"><i class="ic" data-ic="phone"></i>Called Leads<span class="badge" id="calledBadge">0</span></button>
      <button class="nv" data-go="calendar"><i class="ic" data-ic="cal"></i>Calendar</button>
      <button class="nv" data-go="calls"><i class="ic" data-ic="log"></i>Call Log</button>
      <button class="nv" data-go="notes"><i class="ic" data-ic="note"></i>Notes</button>
      <button class="nv" data-go="profits"><i class="ic" data-ic="dollar"></i>Profits</button>
      <button class="nv" data-go="admin" id="navAdmin" style="display:none"><i class="ic" data-ic="shield"></i>Admin</button>
      <button class="nv" data-go="account"><i class="ic" data-ic="gear"></i>Settings</button>
    </nav>
    <div class="foot pop">Leafline Web Services<div class="lgt" data-lgt aria-label="Theme" role="radiogroup"></div></div>
  </aside>

  <section class="main" id="main">
    <header class="top">
      <button class="mav" id="mAvBtn" aria-label="Open settings"><span class="in-av" id="mAv">LF</span></button>
      <h1 id="title" class="pop">Dashboard</h1>
      <div class="srch pop"><i class="ic" data-ic="search"></i><input id="gq" placeholder="Search businesses, owners, phone numbers..." autocomplete="off" aria-label="Search"><kbd>/</kbd></div>
      <div class="lgt pop" data-lgt aria-label="Theme" role="radiogroup"></div>
      <button class="sync pop" id="syncBtn" aria-live="polite"><i></i><span id="syncTx">Sync</span></button>
      <button class="rb pop" id="bellBtn" aria-label="Activity"><i class="ic" data-ic="bell"></i><span class="cnt" id="bellCnt">0</span></button>
      <button class="rb pop" id="scriptBtn" aria-label="Show my script" title="Show my script beside the page (Ctrl+J)"><i class="ic" data-ic="script"></i></button>
      <button class="rb pop" id="userBtn" aria-label="Account"><i class="ic" data-ic="user"></i></button>
      <button class="rb pop" id="outBtn" aria-label="Sign out" title="Sign out"><i class="ic" data-ic="logout"></i></button>
    </header>
    <div class="bell" id="bell"><h4>Recent activity</h4><div id="bellList"></div></div>

    <div class="pages">
      <!-- DASHBOARD -->
      <div class="page on" id="pg-dash"><div class="empty" style="margin-top:90px"><div class="spin"></div><b>Starting up...</b></div></div>

      <!-- FIND -->
      <div class="page flex" id="pg-find">
        <div class="card fcard pop">
          <div class="frow">
            <div><label class="l" for="fCountry">Country</label><input class="inp" id="fCountry" placeholder="Canada"></div>
            <div><label class="l" for="fState">State / Province</label><input class="inp" id="fState" placeholder="Ontario"></div>
            <div><label class="l" for="fCity">City</label><input class="inp" id="fCity" placeholder="Kitchener"></div>
            <div><label class="l" for="fType">Business type</label><input class="inp" id="fType" placeholder="e.g. Home Renovation"></div>
            <button class="btn pri" id="goBtn"><i class="ic" data-ic="search"></i><span>Search</span></button>
          </div>
          <div class="sline"><span id="sText">Enter an area and a business type, then press Search. Businesses you mark move to Called Leads.</span></div>
          <div class="pbar" id="pbar"><i id="pfill"></i></div>
        </div>
        <div class="split">
          <div class="card pane pop">
            <div class="ph">
              <h3>Businesses to call</h3><div class="sub" id="fSub">0 businesses</div>
              <div class="tools">
                <select id="scope" aria-label="Which searches"><option value="current">Current search</option><option value="all">All saved searches</option></select>
                <select id="sort" aria-label="Sort"><option value="reviews">Most reviews</option><option value="open">Open now first</option><option value="name">Name A-Z</option></select>
                <button class="chip" id="openOnly">Open now only</button><button class="chip" id="fExport" title="Save these businesses as a CSV file">Export CSV</button>
                <label class="all"><span>Select all</span><button class="chk" id="allChk" aria-label="Select all"><svg viewBox="0 0 16 16"><path d="M3 8.5l3.2 3L13 4.5"/></svg></button></label>
              </div>
            </div>
            <div class="list" id="list" role="listbox" aria-label="Businesses"></div>
          </div>
          <div class="card pane dpane pop" id="detail"></div>
        </div>
      </div>

      <!-- CALLED -->
      <div class="page" id="pg-called"></div>

      <!-- ACCOUNT -->
      <div class="page" id="pg-account"></div>

      <!-- TEAM -->
      <div class="page" id="pg-team"><div class="empty" style="margin-top:90px"><div class="spin"></div><b>Loading the team...</b></div></div>

      <!-- LEADERBOARD + ANNOUNCEMENTS -->
      <div class="page" id="pg-board"></div>
      <div class="page" id="pg-posts"></div>
      <div class="page" id="pg-msgs"></div>

      <!-- CALENDAR -->
      <div class="page" id="pg-calendar"></div>

      <!-- PROFITS -->
      <div class="page" id="pg-profits"></div>

      <div class="page" id="pg-calls"></div>
      <div class="page flex" id="pg-notes"></div>
      <div class="page" id="pg-admin"></div>

      <!-- SCRIPT DOCK: stays open next to Find Leads / Called Leads -->
      <aside class="dock" id="dock" aria-label="My script">
        <div class="dk-grip" id="dkGrip" title="Drag to resize"></div>
        <div class="dk-head"><select id="dkSel" aria-label="Which script"></select><button id="dkMinus" title="Smaller text" aria-label="Smaller text">A−</button><button id="dkPlus" title="Bigger text" aria-label="Bigger text">A+</button><button id="dkEdit" title="Edit this script" aria-label="Edit script">Edit</button><button id="dkX" title="Close (Ctrl+J)" aria-label="Close script">✕</button></div>
        <input class="dk-find" id="dkFind" placeholder="Find a word in the script" aria-label="Find in script" autocomplete="off">
        <div class="dk-body"><div class="paper" id="dkPaper"><div class="rte read" id="dkBody"></div></div></div>
      </aside>
    </div>

    <div class="fnav pop" id="fnav">
      <div class="fpill" id="fpill"><div class="flamp" id="flamp"></div><div class="fbg" id="fbg"></div><div class="fthumb" id="fthumb"></div>
        <button data-go="dash"><i class="ic" data-ic="home"></i><span>Home</span></button><button data-go="team" class="fx"><i class="ic" data-ic="users"></i><span>Team</span></button><button data-go="board" class="fx"><i class="ic" data-ic="trophy"></i><span>Ranks</span></button><button data-go="posts" class="fx"><i class="ic" data-ic="mega"></i><span>News</span></button><button data-go="msgs" class="fmsg"><i class="ic" data-ic="chat"></i><span>Messages</span><i class="ndot" id="fnMsgDot"></i></button><button data-go="find"><i class="ic" data-ic="search"></i><span>Leads</span></button><button data-go="called"><i class="ic" data-ic="phone"></i><span>Called</span></button><button data-go="calendar"><i class="ic" data-ic="cal"></i><span>Calendar</span></button><button data-go="calls" class="fx"><i class="ic" data-ic="log"></i><span>Calls</span></button><button data-go="notes" class="fx"><i class="ic" data-ic="note"></i><span>Notes</span></button><button data-go="profits" class="fx"><i class="ic" data-ic="dollar"></i><span>Profits</span></button><button data-go="admin" class="fx" id="fnAdmin" style="display:none"><i class="ic" data-ic="shield"></i><span>Admin</span></button><button data-go="account" class="fx"><i class="ic" data-ic="gear"></i><span>Settings</span></button><button class="fmore" id="fmore" aria-label="More pages"><i class="ic" data-ic="grid"></i><span>More</span><i class="ndot" id="moreDot"></i></button>
      </div>
      <button class="fplus" id="fplus" aria-label="New search"><i class="ic" data-ic="plus"></i></button>
    </div>
  </section>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"><span id="tMsg"></span></div>
<div class="sheet" id="msheet" aria-hidden="true"><div class="sbk" data-close></div><div class="sp" role="dialog" aria-label="All pages"><div class="grab"></div><div class="sg" id="sheetGrid"></div>
  <div class="sx"><div class="lgt" data-lgt aria-label="Theme" role="radiogroup"></div><button class="btn sm" id="sheetBell"><i class="ic" data-ic="bell"></i>Activity</button><button class="btn sm" id="sheetOut"><i class="ic" data-ic="logout"></i>Sign out</button></div></div></div>
<div id="login" role="dialog" aria-modal="true" aria-label="Sign in">
  <div class="card lg">
    <div class="mark" id="lgMark"><svg class="mk" viewBox="0 0 64 64" aria-hidden="true"><defs><linearGradient id="lgB" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B8F7D4"/><stop offset=".55" stop-color="#4ADE8B"/><stop offset="1" stop-color="#1F9E5B"/></linearGradient></defs><path d="M51 9C30 9 13 20 13 39c0 6 2 11 5 15 2-12 9-22 21-29-9 8-15 18-17 30 4 2 8 3 12 3 19 0 26-19 26-37 0-5-1-9-9-12z" fill="url(#lgB)"/><path d="M22 55c3-13 10-23 21-30" fill="none" stroke="rgba(4,33,15,.45)" stroke-width="2.2" stroke-linecap="round"/></svg></div>
    <form id="lgForm" autocomplete="on">
      <h2>Welcome to Leafline</h2><p class="sub">Sign in with your own account. Everyone on the team works from the same shared data.</p>
      <label class="l" for="lgUser">Username</label><input class="inp" id="lgUser" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="e.g. gio">
      <label class="l" for="lgPass">Password</label><input class="inp" id="lgPass" type="password" autocomplete="current-password">
      <div class="err" id="lgErr" role="alert"></div>
      <button class="btn pri" id="lgGo" type="submit">Sign in</button>
    </form>
    <form id="pwForm" style="display:none" autocomplete="off">
      <h2>Choose a new password</h2><p class="sub">Your starter password was temporary. Pick a new one (at least 8 characters, with a letter and a number) to continue.</p>
      <label class="l" for="pwNew">New password</label><input class="inp" id="pwNew" type="password" autocomplete="new-password">
      <label class="l" for="pwNew2">Type it again</label><input class="inp" id="pwNew2" type="password" autocomplete="new-password">
      <div class="err" id="pwErr" role="alert"></div>
      <button class="btn pri" id="pwGo" type="submit">Save and continue</button>
    </form>
  </div>
</div>

<script>
"use strict";
/* ---------------- helpers ---------------- */
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const REDUCE=matchMedia("(prefers-reduced-motion: reduce)").matches;
const ICONS={
 mega:'<path d="M4 10v4a1 1 0 001 1h2l5 4V5L7 9H5a1 1 0 00-1 1z"/><path d="M16 8.5a5 5 0 010 7M19 6a8.5 8.5 0 010 12"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
 grid:'<rect x="4" y="4" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="2"/>',
 crown:'<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5z"/><path d="M5 19h14"/>',
 flame:'<path d="M12 21c-4 0-7-2.7-7-6.5 0-3 2-5 3.5-6.5.3 1.6 1.2 2.7 2.5 3.2C11 7.8 12.5 5 15 3c-.3 3 1 4.5 2.4 6.2A7.5 7.5 0 0119 14.5C19 18.3 16 21 12 21z"/>',
 rocket:'<path d="M14 4c3-1.5 5.5-1 6-.5.5.5 1 3-.5 6L13 16l-5-5z"/><path d="M8 11l-3 1-2 3 4 1M13 16l-1 3-3 2-1-4"/><circle cx="15.5" cy="8.5" r="1.5"/>',
 hand:'<path d="M3 12l4-4 4 2 3-2 7 6-3 3-4-3-2 2"/><path d="M7 8l-4 4 6 6 3-3M11 15l3 3M13 13l3 3"/>',
 bulb:'<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z"/>',
 spark:'<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/><path d="M19 3v4M17 5h4"/>',
 send:'<path d="M21 3L10 14"/><path d="M21 3l-7 18-4-7-7-4z"/>',
 dots:'<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
 chat:'<path d="M4 5h16v11H9l-5 4z"/>',
 note:'<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 13h7M9 17h5"/>',
 log:'<path d="M5 4h14v16H5z"/><path d="M9 9h6M9 13h6M9 17h3"/>',
 shield:'<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
 script:'<path d="M5 4h10a3 3 0 013 3v13H8a3 3 0 01-3-3z"/><path d="M9 8h5M9 12h5"/>',
 logout:'<path d="M9 4H5a2 2 0 00-2 2v12a2 2 0 002 2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
 home:'<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
 phone:'<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
 bell:'<path d="M6 16V11a6 6 0 1112 0v5l2 2H4z"/><path d="M10 21h4"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 copy:'<rect x="9" y="9" width="11" height="11" rx="3"/><path d="M5 15V6a2 2 0 012-2h9"/>',
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
 users:'<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14.5c2.5.6 4 2.3 4 5.5"/>',
 check:'<path d="M4 12.5l5 5L20 6.5"/>',
 cal:'<rect x="3" y="5" width="18" height="16" rx="4"/><path d="M3 10h18M8 3v4M16 3v4"/>',
 pct:'<path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
 down:'<path d="M12 4v12M6 12l6 6 6-6"/>',
 undo:'<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
 dollar:'<path d="M12 3v18"/><path d="M16.5 7.6C15.8 6.3 14.2 5.5 12 5.5c-2.6 0-4.2 1.2-4.2 3s1.4 2.6 4.2 3.2 4.2 1.4 4.2 3.2-1.7 3-4.2 3c-2.3 0-4-.9-4.7-2.4"/>',
 edit:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
 trash:'<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
 star:'<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
 flag:'<path d="M5 21V4"/><path d="M5 4h12l-2 4 2 4H5"/>',
 heart:'<path d="M12 20s-7-4.6-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.4-7 10-7 10z"/>',
 bolt:'<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>',
 briefcase:'<rect x="3" y="7" width="18" height="13" rx="3"/><path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18"/>',
 gift:'<rect x="3" y="9" width="18" height="11" rx="2"/><path d="M12 9v11M3 13h18"/><path d="M12 9c-3 0-4-4-1.5-4S12 9 12 9zM12 9c3 0 4-4 1.5-4S12 9 12 9z"/>',
 video:'<rect x="3" y="6" width="12" height="12" rx="3"/><path d="M15 10l6-3v10l-6-3"/>',
 pin:'<path d="M12 21s-6-5.5-6-11a6 6 0 0112 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>',
 mail:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 8l9 6 9-6"/>',
 coffee:'<path d="M4 9h12v5a5 5 0 01-5 5H9a5 5 0 01-5-5z"/><path d="M16 11h2a2 2 0 010 4h-2M8 3v3M12 3v3"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 trophy:'<path d="M8 4h8v5a4 4 0 01-8 0z"/><path d="M8 6H5a3 3 0 003 4M16 6h3a3 3 0 01-3 4M12 13v4M8 20h8M9 17h6"/>',
 repeat:'<path d="M17 3l3 3-3 3"/><path d="M4 11V9a3 3 0 013-3h13M7 21l-3-3 3-3"/><path d="M20 13v2a3 3 0 01-3 3H4"/>',
 prev:'<path d="M15 5l-7 7 7 7"/>',
 next:'<path d="M9 5l7 7-7 7"/>'
};
const ic=n=>`<i class="ic">${svg(n)}</i>`;
const svg=n=>`<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]||""}</svg>`;
function hydrateIcons(root=document){$$("i.ic[data-ic]",root).forEach(e=>{e.innerHTML=svg(e.dataset.ic);e.removeAttribute("data-ic")})}
const TYPE_COLORS=["#3DDC84","#5EE6B8","#FFD60A","#FF9F43","#F2788A","#7FB6FF"];
const hue=s=>{let h=0;for(const c of String(s||""))h=(h*31+c.charCodeAt(0))>>>0;return TYPE_COLORS[h%TYPE_COLORS.length]};
const initials=n=>{const w=String(n||"").replace(/[^A-Za-z0-9 ]/g," ").split(/\s+/).filter(Boolean);return ((w[0]||"?").charAt(0)+(w[1]||"").charAt(0)).toUpperCase()};
const ST={green:{k:"green",label:"Meeting set up",cls:"g",color:"#3FD487",tint:"#1F5A3A"},yellow:{k:"yellow",label:"Interested",cls:"y",color:"#E9C15A",tint:"#4A431A"},
 orange:{k:"orange",label:"No answer",cls:"o",color:"#EB955A",tint:"#4B2E16"},red:{k:"red",label:"Not interested",cls:"r",color:"#E46F6F",tint:"#4A1C1C"}};
const ORDER=["green","yellow","orange","red"];
const initialsOf=n=>String(n||"?").split(/\s+/).map(w=>w[0]).join("").slice(0,2).toUpperCase();
const fmtDate=s=>{if(!s)return"";const d=new Date(s.replace(" ","T"));if(isNaN(d))return s;return d.toLocaleDateString("en-US",{month:"short",day:"numeric"})+" · "+d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})};
const num=n=>Number(n||0).toLocaleString("en-US");
const NA="N/A";

/* ---------------- animation: pop-in for everything that enters view ---------------- */
const io=new IntersectionObserver(es=>{
  const vis=es.filter(e=>e.isIntersecting).map(e=>e.target);
  vis.forEach(t=>io.unobserve(t));
  vis.sort((a,b)=>{const A=a.getBoundingClientRect(),B=b.getBoundingClientRect();return (A.top-B.top)||(A.left-B.left)});
  vis.forEach((el,i)=>popIn(el,Math.min(i,16)*40));
},{threshold:.04});
function popIn(el,delay=0){
  const quiet=el.dataset.quiet;el.classList.add("in");
  if(quiet){delete el.dataset.quiet;return}
  if(REDUCE)return;
  el.animate([{opacity:0,transform:"translateY(14px) scale(.97)"},{opacity:1,transform:"translateY(-2px) scale(1.006)",offset:.6},{opacity:1,transform:"none"}],
    {duration:640,delay,easing:"cubic-bezier(.22,1,.36,1)",fill:"backwards"});
}
new MutationObserver(ms=>ms.forEach(m=>m.addedNodes.forEach(n=>{
  if(n.nodeType!==1)return;if(n.classList.contains("pop"))io.observe(n);n.querySelectorAll&&n.querySelectorAll(".pop").forEach(e=>io.observe(e))
}))).observe(document.body,{childList:true,subtree:true});
function arm(root){$$(".pop",root).forEach(e=>{e.classList.remove("in");io.observe(e)})}
function quiet(root){$$(".pop",root).forEach(e=>{e.dataset.quiet=1;e.classList.add("in")})}
function bump(el){if(!el||REDUCE)return;el.animate([{transform:"scale(.9)"},{transform:"scale(1.05)",offset:.55},{transform:"scale(1)"}],{duration:520,easing:"cubic-bezier(.22,1,.36,1)"})}
function countTo(el,to,dec=0,suffix="",ms=1000){
  if(!el)return;const fmtN=v=>dec?v.toLocaleString("en-US",{minimumFractionDigits:dec,maximumFractionDigits:dec}):num(Math.round(v));const fin=()=>el.textContent=fmtN(to)+suffix;
  if(REDUCE||el.dataset.q){fin();return}
  const t0=performance.now();(function f(t){const p=Math.min(1,(t-t0)/ms),e=1-Math.pow(1-p,3),v=to*e;
    el.textContent=fmtN(v)+suffix;if(p<1)requestAnimationFrame(f);else fin()})(t0);
}

/* ---------------- state + python bridge ---------------- */
const S={page:"dash",deals:[],profile:{},stats:null,find:[],called:[],scope:"all",sort:"reviews",openOnly:false,q:"",sel:new Set(),active:null,
 running:false,current:null,notes:[],unread:0,ready:false,type:"all",dirty:false,lastSig:{}};
const TOKEN=new URLSearchParams(location.search).get("t")||"";
const api=window.LF_API||(async(n,...a)=>{const r=await fetch("/api/"+n+"?t="+encodeURIComponent(TOKEN),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(a)});
  let d=null;try{d=await r.json()}catch(e){}
  if(!r.ok)throw new Error((d&&d.error)||"The app engine returned an error ("+r.status+").");return d});
if(window.LF_API)document.documentElement.classList.add("web");

/* ---------------- toast, dialogs, bell ---------------- */
let toastT=null;
function toast(msg,o={}){
  const t=$("#toast");$("#tMsg").textContent=msg;$$("button",t).forEach(b=>b.remove());t.classList.toggle("bad",!!o.bad);
  if(o.action){const b=document.createElement("button");b.textContent=o.action.label;b.onclick=()=>{hideToast();o.action.fn()};t.appendChild(b)}
  t.classList.add("on");clearTimeout(toastT);toastT=setTimeout(hideToast,o.ms||(o.action?6000:2800));
}
const hideToast=()=>$("#toast").classList.remove("on");
function logNote(text){S.notes.unshift({text,t:new Date()});S.notes=S.notes.slice(0,20);S.unread++;renderBell()}
function renderBell(){
  const c=$("#bellCnt");c.textContent=S.unread;c.classList.toggle("on",S.unread>0);
  $("#bellList").innerHTML=S.notes.length?S.notes.map(n=>`<div class="it">${esc(n.text)}<small>${n.t.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})}</small></div>`).join(""):'<div class="muted" style="padding:8px 6px">No activity yet. Searches and calls you log will show up here.</div>';
}
function openModal(html,mount){
  const ov=document.createElement("div");ov.className="ov";ov.innerHTML=`<div class="dlg" role="dialog" aria-modal="true">${html}</div>`;
  document.body.appendChild(ov);hydrateIcons(ov);requestAnimationFrame(()=>requestAnimationFrame(()=>ov.classList.add("on")));
  const close=()=>{ov.classList.remove("on");setTimeout(()=>ov.remove(),300);document.removeEventListener("keydown",key)};
  const key=e=>{if(e.key==="Escape")close()};document.addEventListener("keydown",key);
  ov.addEventListener("mousedown",e=>{if(e.target===ov)close()});
  mount&&mount(ov,close);const f=$("input,textarea,button.btn",ov);f&&setTimeout(()=>f.focus(),120);return close;
}
function alertBox(title,msg){openModal(`<h2>${esc(title)}</h2><p class="muted" style="margin:10px 0 20px;line-height:1.55;white-space:pre-wrap">${esc(msg)}</p><div style="text-align:right"><button class="btn pri" data-x>OK</button></div>`,(ov,close)=>$("[data-x]",ov).onclick=close)}
function copyText(t){
  const done=()=>toast("Phone number copied");
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(done,()=>fb())}else fb();
  function fb(){const a=document.createElement("textarea");a.value=t;a.style.cssText="position:fixed;opacity:0";document.body.appendChild(a);a.select();try{document.execCommand("copy");done()}catch(e){toast("Couldn't copy",{bad:1})}a.remove()}
}

/* ---------------- data helpers ---------------- */
const match=l=>{if(!S.q)return true;const q=S.q.toLowerCase();return (l.name+" "+l.phone+" "+l.owner+" "+l.btype+" "+l.address).toLowerCase().includes(q)};
const openPill=l=>`<span class="pill ${l.open}">${l.open==="open"?"Open now":l.open==="closed"?"Closed":"Hours N/A"}</span>`;
const reviewTxt=l=>l.reviews===NA?"No reviews yet":"★ "+(l.rating===NA?"":l.rating+" · ")+num(l.reviews)+" review"+(+l.reviews===1?"":"s");
const hoursShort=l=>l.hours&&l.hours!==NA?(l.hours==="Closed"?"Closed today":l.hours):"Hours N/A";
const hoursTxt=l=>l.hours&&l.hours!==NA?(l.hours==="Closed"?"Closed today":"Today "+l.hours)+(l.open_note?" · "+l.open_note:""):"Hours N/A";
function visibleFind(){
  let a=S.find.filter(match);if(S.openOnly)a=a.filter(l=>l.open==="open");
  const rv=l=>parseInt(l.reviews)||0,rank={open:0,unknown:1,closed:2};
  if(S.sort==="name")a.sort((x,y)=>x.name.localeCompare(y.name));
  else if(S.sort==="open")a.sort((x,y)=>(rank[x.open]-rank[y.open])||(rv(y)-rv(x))||x.name.localeCompare(y.name));
  else a.sort((x,y)=>(rv(y)-rv(x))||x.name.localeCompare(y.name));
  return a;
}
let reloadTok=0;
async function reload(){
  const my=++reloadTok;
  try{
    const [f,c,s,dl]=await Promise.all([api("get_find",S.scope),api("get_called"),api("stats"),api("get_deals")]);
    if(my!==reloadTok)return;     // a newer reload is already running; never let an older answer overwrite it
    S.find=f;S.called=c;S.stats=s;S.deals=dl;S.q=$("#gq").value.trim();
    renderAll(true);
  }catch(e){}
}

/* ---------------- sidebar, nav pills ---------------- */
const IMG_OK=/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+\/=]+$/;
const safeImg=u=>(typeof u==="string"&&u.length<62000&&IMG_OK.test(u))?u:"";
function paintAv(e,name,color,img,media){
  const {src,still}=avSrc(img,media),h=esc(name?initials(name):"LF")+imgTag(src,still);
  if(e.dataset.h!==h){e.innerHTML=h;e.dataset.h=h}
  e.style.background=`linear-gradient(150deg,${color||"#4ADE8B"}55,var(--av-bg))`;
}
function avHTML(name,img,media){const {src,still}=avSrc(img,media);return `<span class="tav">${esc(initials(name||"?"))}${imgTag(src,still)}</span>`}
/* Still copy of a picture, as sharp as the shared database allows: WebP when the browser can make it, else JPEG.
   Pictures: up to 512 px square. Banners: up to 1500 x 375. Steps down in quality, then size, until it fits. */
function fitStill(im,banner,limit){
  const iw=im.naturalWidth,ih=im.naturalHeight,c=document.createElement("canvas"),x=c.getContext("2d");
  const probe=document.createElement("canvas");probe.width=probe.height=1;const webp=probe.toDataURL("image/webp").startsWith("data:image/webp");
  const type=webp?"image/webp":"image/jpeg";
  for(const W of banner?[1500,1200,960,720]:[512,448,384,320,256]){
    const H=banner?Math.round(W/4):W;c.width=W;c.height=H;x.imageSmoothingEnabled=true;x.imageSmoothingQuality="high";x.fillStyle="#183626";x.fillRect(0,0,W,H);
    if(banner){const k=Math.max(W/iw,H/ih),w=iw*k,h=ih*k;x.drawImage(im,(W-w)/2,(H-h)/2,w,h)}
    else{const n=Math.min(iw,ih);x.drawImage(im,(iw-n)/2,(ih-n)/2,n,n,0,0,W,W)}
    for(let q=.92;q>=.5;q-=.07){const d=c.toDataURL(type,q);if(d.length<=limit)return d}
  }
  throw new Error("That picture is too detailed. Try another.");
}
function pictureFromFile(file){
  return new Promise((res,rej)=>{
    if(!file||!/^image\//.test(file.type))return rej(new Error("Pick an image file (JPG, PNG or WebP)."));
    if(file.size>15e6)return rej(new Error("That image is too big. Pick one under 15 MB."));
    const url=URL.createObjectURL(file),im=new Image();
    im.onload=()=>{try{URL.revokeObjectURL(url);res(fitStill(im,0,58000))}catch(e){rej(e)}};
    im.onerror=()=>{URL.revokeObjectURL(url);rej(new Error("Couldn't read that picture. Try a JPG or PNG."))};im.src=url});
}
function profileUI(){
  const p=S.profile,ini=p.name?initials(p.name):"LF";
  $$("#sideAv,#mAv,.in-av[data-live]").forEach(e=>paintAv(e,p.name,p.color,S.me&&S.me.avatar,S.me&&S.me.media));
  $("#hiTxt").innerHTML=p.name?`Hi, ${esc(p.name.split(" ")[0])}! 👋`:"Hi there! 👋";
}
function movePills(){
  const on=$("#nav .nv.on");if(on){const p=$("#navPill");p.style.top=on.offsetTop+"px";p.style.height=on.offsetHeight+"px"}
  let fb=$("#fpill button.on[data-go]");const mo=$("#fmore");if((!fb||!fb.offsetWidth)&&mo&&mo.offsetWidth)fb=mo;if(mo)mo.classList.toggle("on",fb===mo);
  if(fb){const L=$("#flamp");L.style.left=fb.offsetLeft+"px";L.style.width=fb.offsetWidth+"px";L.classList.add("on");
    const t=$("#fthumb");if(t){t.style.left=(fb.offsetLeft+fb.offsetWidth*.3)+"px";t.style.width=(fb.offsetWidth*.4)+"px"}
    const fp=$("#fpill");if(fp.scrollWidth>fp.clientWidth+2)fp.scrollTo({left:Math.max(0,fb.offsetLeft-(fp.clientWidth-fb.offsetWidth)/2),behavior:"smooth"})}
}
const TITLES={dash:"Dashboard",team:"Team",board:"Leaderboard",posts:"Announcements",msgs:"Messages",find:"Find Leads",called:"Called Leads",calendar:"Calendar",calls:"Call Log",notes:"Notes & Scripts",profits:"Profits",admin:"Admin",account:"Settings"};
let navToken=0;
async function go(p,force){
  if(p===S.page&&!force)return;
  if(S.page==="notes"&&p!=="notes"){await flushNote();document.body.classList.remove("focus")}
  const my=++navToken,old=$(".page.on"),next=$("#pg-"+p);
  S.page=p;closeSheet();hideHover(true);
  document.body.className=document.body.className.replace(/\bp-\w+/g,"").trim()+" p-"+p;
  $$("[data-go]").forEach(b=>b.classList.toggle("on",b.dataset.go===p));movePills();
  const t=$("#title");t.animate([{opacity:1,transform:"none"},{opacity:0,transform:"translateY(-8px)"}],{duration:140,easing:EASE.in,fill:"forwards"}).finished.then(()=>{if(my!==navToken)return;t.textContent=TITLES[p];t.getAnimations().forEach(a=>a.cancel());t.animate([{opacity:0,transform:"translateY(10px)",filter:"blur(4px)"},{opacity:1,transform:"none",filter:"blur(0)"}],{duration:460,easing:EASE.out})}).catch(()=>{});
  if(old&&old!==next&&!REDUCE){try{await old.animate([{opacity:1,transform:"none"},{opacity:0,transform:"translateY(8px) scale(.99)"}],{duration:170,easing:EASE.in,fill:"forwards"}).finished}catch(e){}}
  if(my!==navToken)return;
  if(old){old.getAnimations().forEach(a=>a.cancel());old.classList.remove("on")}
  S.lastSig={};
  if(p==="dash")renderDash(false);if(p==="team")renderTeam();if(p==="called")renderBoard(false);if(p==="account")renderAccount();if(p==="profits")renderProfits(false);if(p==="calendar")renderCalendar(false);if(p==="calls")renderCalls();if(p==="notes")renderNotes();if(p==="admin")renderAdmin();if(p==="find"){renderFind();paintLeadgenFind()}if(p==="board")renderRanks(false);if(p==="posts")renderPosts();if(p==="msgs")renderMsgs();else if(typeof mxLeave==="function")mxLeave();
  arm(next);next.classList.add("on");applyDock();
  if(!REDUCE)next.animate([{opacity:0,transform:"translateY(14px)"},{opacity:1,transform:"none"}],{duration:480,easing:EASE.out});
  history.replaceState(null,"","#"+p);
  if(p==="find"){const l=$("#list");l.scrollTop=0}
}
/* ---------------- DASHBOARD ---------------- */
function greet(){const h=new Date().getHours();return h<12?"Good morning":h<18?"Good afternoon":"Good evening"}
function spark(vals,color){
  const W=96,H=38,n=vals.length,mx=Math.max(...vals,1),mn=Math.min(...vals,0),r=(mx-mn)||1;
  const pts=vals.map((v,i)=>[n>1?i*(W/(n-1)):0,H-4-((v-mn)/r)*(H-8)]);
  let d="M"+pts[0][0].toFixed(1)+","+pts[0][1].toFixed(1);
  for(let i=1;i<n;i++){const [x0,y0]=pts[i-1],[x1,y1]=pts[i],cx=(x0+x1)/2;d+=` C${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`}
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${d}" pathLength="1" stroke="${color}"/></svg>`;
}
function illustration(){return `<svg class="ill" viewBox="0 0 520 170" aria-hidden="true">
 <rect x="30" y="16" width="250" height="138" rx="26" fill="#EAF7EF"/><rect x="30" y="16" width="250" height="34" rx="17" fill="#CDEBDA"/>
 <circle cx="56" cy="33" r="5" fill="#FF8A8F"/><circle cx="74" cy="33" r="5" fill="#FFD60A"/><circle cx="92" cy="33" r="5" fill="#34D27B"/>
 <rect x="58" y="96" width="30" height="42" rx="9" fill="#7FB6FF"/><rect x="100" y="72" width="30" height="66" rx="9" fill="#FF9F43"/><rect x="142" y="84" width="30" height="54" rx="9" fill="#F2788A"/><rect x="184" y="62" width="30" height="76" rx="9" fill="#34D27B"/>
 <circle cx="244" cy="100" r="26" fill="none" stroke="#34D27B" stroke-width="12"/><path d="M244 74a26 26 0 0126 26" fill="none" stroke="#FFD60A" stroke-width="12"/>
 <ellipse cx="330" cy="142" rx="38" ry="10" fill="#0E2A1B" opacity=".5"/><circle cx="330" cy="126" r="18" fill="#FFD60A"/><circle cx="330" cy="126" r="11" fill="none" stroke="#C99F00" stroke-width="3"/>
 <path d="M440 150h64l-8 -50h-48z" fill="#E7C9A0"/><rect x="432" y="94" width="80" height="14" rx="7" fill="#D8B386"/>
 <path d="M472 94C440 80 436 50 452 30 470 46 478 70 472 94z" fill="#34D27B"/><path d="M474 94C500 84 514 60 504 38 484 52 474 72 474 94z" fill="#2BB567"/><path d="M473 94C470 70 480 44 490 22 498 50 490 74 473 94z" fill="#5EE6B8"/></svg>`}
const usd=n=>{n=+n||0;return "$"+n.toLocaleString("en-US",{minimumFractionDigits:Number.isInteger(n)?0:2,maximumFractionDigits:2})};
const dayFmt=s=>{const d=new Date(s+"T00:00:00");return isNaN(d)?String(s||""):d.toLocaleDateString("en-US",{month:"short",day:"numeric"})};
const isoDay=d=>d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
const terms=d=>{const a=[];if(d.upfront>0)a.push(usd(d.upfront)+" upfront");if(d.monthly>0)a.push(usd(d.monthly)+"/mo"+(d.months?" × "+d.months:", ongoing"));return a.join(" + ")};
function moneyTile(m){
  if(!m)return "";
  const mo=m.month,W=240,H=64,n=mo.days;let c=0,c2=0;const cum=mo.daily.map(v=>(c+=v)),cm=(mo.daily_made||mo.daily).map(v=>(c2+=v));
  const mx=Math.max(mo.total,1),X=i=>n>1?i*(W/(n-1)):0,Y=v=>H-5-(H-12)*v/mx,t=Math.min(Math.max(mo.today,1),n)-1;
  const made=cm.slice(0,t+1).map((v,i)=>(i?"L":"M")+X(i).toFixed(1)+","+Y(v).toFixed(1)).join(" ");
  const proj=[cm[t]].concat(cum.slice(t+1)).map((v,i)=>(i?"L":"M")+X(t+i).toFixed(1)+","+Y(v).toFixed(1)).join(" ");
  const pct=mo.total>0?Math.round(100*mo.made/mo.total):0,dec=Number.isInteger(mo.made)?0:2;
  return `<button class="mtile" data-go="profits" aria-label="Open Profits"><div class="mk"><span>Made in ${esc(mo.label.split(" ")[0])}</span><span>${pct}%</span></div>
   <div class="mv"><small>$</small><span class="vl" data-n="${mo.made}" data-d="${dec}" data-s="">0</span></div>
   <div class="tr"><div class="fl" data-w="${pct}"></div></div>
   <div class="ms">${mo.total>0?`${usd(mo.rest)} more scheduled this month`:"Add a deal in Profits to start tracking"}</div>
   <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Money made so far this month"><line x1="0" x2="${W}" y1="${H-1}" y2="${H-1}" stroke="rgba(255,255,255,.18)"/>
    <path class="marea" d="${made} L${X(t).toFixed(1)},${H-1} L0,${H-1} Z" fill="rgba(61,220,132,.30)"/>
    <path class="mproj" d="${proj}" fill="none" stroke="#CFE7D8" stroke-width="2" stroke-dasharray="4 5" stroke-linecap="round"/>
    <path class="mline" pathLength="1" d="${made}" fill="none" stroke="#7DF0A8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <circle class="mdot" style="--i:4" cx="${X(t).toFixed(1)}" cy="${Y(cm[t]).toFixed(1)}" r="5" fill="#FFD60A" stroke="#153a28" stroke-width="2"/></svg></button>`;
}
function renderDash(q){
  const st=S.stats;if(!st)return;const p=S.profile,pg=$("#pg-dash"),sig=JSON.stringify([st,p.name,p.goal]);
  if(q&&S.lastSig.dash===sig)return;S.lastSig.dash=sig;
  const w=st.week,sg=st.series,pct=Math.min(100,Math.round(100*st.today_calls/Math.max(1,st.goal)));
  const mxT=Math.max(...st.types.map(t=>t.count),1),totT=st.types.reduce((a,t)=>a+t.count,0)||1;
  const sCards=[
   {c:"s1",tone:"tone-g",ico:"users",ib:"#2BB567",lb:"Total leads",v:st.total,dec:0,suf:"",dl:`+${num(w.added)} this week`,sp:sg.added,col:"var(--accent-hi)"},
   {c:"s2",tone:"tone-y",ico:"phone",ib:"#C9A400",lb:"Businesses called",v:st.called,dec:0,suf:"",dl:`+${num(w.calls)} this week`,sp:sg.calls,col:"#FFD60A"},
   {c:"s3",tone:"tone-g",ico:"cal",ib:"#1FA64A",lb:"Meetings set up",v:st.meetings,dec:0,suf:"",dl:`+${num(w.meets)} this week`,sp:sg.meets,col:"#9CF2C3"},
   {c:"s4",tone:"tone-o",ico:"pct",ib:"#E8680C",lb:"Meeting rate",v:st.conversion,dec:1,suf:"%",dl:`${w.conv>=0?"+":""}${w.conv}% this week`,sp:sg.conv,col:"#FFB070"}];
  pg.innerHTML=`
  <div class="banner pop"><div>${illustration()}</div><div>
    <h2>${greet()}${p.name?", "+esc(p.name.split(" ")[0]):""}!</h2>
    <p>${st.uncalled?`You have <b>${num(st.uncalled)}</b> business${st.uncalled===1?"":"es"} ready to call`:"Nothing on your call list yet"}${st.meetings?` and <b>${num(st.meetings)}</b> meeting${st.meetings===1?"":"s"} set up`:""}.</p>
    <div class="goal"><span>Today's calls: ${st.today_calls} of ${st.goal}</span><div class="tr"><div class="fl" data-w="${pct}"></div></div><span>${pct}%</span></div>
    <button class="btn pri" data-go="find"><i class="ic">${svg(window.LF_API?"phone":"plus")}</i>${window.LF_API?"Start calling":"Find new leads"}</button></div>${moneyTile(st.money)}</div>
  <div class="stats">${sCards.map(c=>`<div class="stat ${c.c} pop"><div class="ico ${c.tone||"tone-g"}"><i class="ic">${svg(c.ico)}</i></div>${spark(c.sp,c.col)}<div class="lb">${c.lb}</div><div class="vl" data-n="${c.v}" data-d="${c.dec}" data-s="${c.suf}">0</div><div class="dl">${c.dl}</div></div>`).join("")}</div>
  <div class="two"><div class="card chart-c pop"><div class="hd"><h3>Activity, last 7 days</h3><div class="legend"><span><i style="background:var(--accent)"></i>Calls</span><span><i style="background:#E9C15A"></i>Meetings set up</span></div></div>
    ${barChart({labels:st.labels,hi:6,aria:"Calls and meetings per day for the last 7 days",series:[{v:sg.calls,c:"b0",name:"Calls"},{v:sg.meets,c:"b1",name:"Meetings"}],tips:sg.calls.map((v,k)=>`${num(v)} call${v===1?"":"s"} · ${num(sg.meets[k])} meeting${sg.meets[k]===1?"":"s"}`)})}</div>
   <div class="card types pop"><div class="hd"><h3>Lead types</h3><span class="muted" style="font-size:12.5px;font-weight:600">${num(st.total)} total</span></div>
    ${st.types.length?st.types.map((t,i)=>`<div class="trow"><div class="tt"><span>${esc(t.name)}</span><span>${num(t.count)} · ${Math.round(100*t.count/totT)}%</span></div><div class="bt"><div class="bf" data-w="${Math.round(100*t.count/mxT)}" style="background:${hue(t.name)}"></div></div></div>`).join(""):`<div class="empty"><div class="bub">${ic("search")}</div><b>No leads yet</b>Run a search on Find Leads.</div>`}</div></div>`;
  hydrateIcons(pg);
  const fire=()=>{$$("[data-w]",pg).forEach(e=>e.style.width=e.dataset.w+"%");$$(".vl",pg).forEach(e=>{if(q)e.dataset.q=1;countTo(e,+e.dataset.n,+e.dataset.d,e.dataset.s)})};
  if(q){quiet(pg);fire()}else setTimeout(fire,350);
}
/* ---------------- FIND ---------------- */
function mkItem(){
  const n=document.createElement("div");n.className="li pop";n.tabIndex=0;n.setAttribute("role","option");
  n.innerHTML=`<button class="chk" aria-label="Select this business"><svg viewBox="0 0 16 16"><path d="M3 8.5l3.2 3L13 4.5"/></svg></button><div class="av"></div><div class="lm"><div class="lt"><b></b><span class="op"></span></div><div class="ls"><span class="ty"></span><span class="hr"></span><span class="rv"></span></div></div>`;
  return n;
}
function fillItem(n,l){
  n.dataset.id=l.id;const av=$(".av",n);av.textContent=initials(l.name);av.style.background=hue(l.btype);
  $("b",n).textContent=l.name;const ph=$(".ty",n);ph.textContent=l.phone;
  const rv=$(".rv",n),rt=reviewTxt(l);if(rv.textContent!==rt){rv.textContent=rt;rv.classList.toggle("none",l.reviews===NA)}
  const hr=$(".hr",n),h=hoursShort(l);if(hr.textContent!==h)hr.textContent=h;
  const op=$(".op",n),pl=openPill(l);if(op.dataset.v!==pl){op.dataset.v=pl;op.innerHTML=pl}
  n.classList.toggle("act",S.active===l.id);n.classList.toggle("sel",S.sel.has(l.id));n.setAttribute("aria-selected",S.active===l.id);
  const sep=n.querySelector(".ls");sep.title=l.btype+" · "+(l.hours||"");
}
function renderFind(){
  const arr=visibleFind(),list=$("#list"),have=new Map($$(".li",list).map(n=>[n.dataset.id,n]));
  const keep=new Set(arr.map(l=>l.id));
  have.forEach((n,id)=>{if(!keep.has(id)){n.remove();have.delete(id)}});
  $$(".empty",list).forEach(e=>e.remove());
  arr.forEach((l,i)=>{let n=have.get(l.id);if(!n){n=mkItem();have.set(l.id,n)}fillItem(n,l);if(list.children[i]!==n)list.insertBefore(n,list.children[i]||null)});
  if(!arr.length){
    const e=document.createElement("div");e.className="empty pop";
    e.innerHTML=S.running?`<div class="spin"></div><b>Searching Google Maps...</b>Businesses appear here as they are found.`:
      S.find.length?`<div class="bub">${ic("search")}</div><b>Nothing matches</b>Try clearing the search box or the "Open now only" filter.`:
      `<div class="bub">${ic("search")}</div><b>No businesses to call yet</b>Enter an area and a business type above, then press Search.`;
    list.appendChild(e);
  }
  if(S.active&&!keep.has(S.active)){S.active=arr[0]?arr[0].id:null}
  if(!S.active&&arr[0])S.active=arr[0].id;
  const total=S.find.length,openN=S.find.filter(l=>l.open==="open").length;
  $("#fSub").textContent=`${num(total)} business${total===1?"":"es"} to call · ${num(openN)} open now`;
  S.sel.forEach(id=>{if(!S.find.some(l=>l.id===id))S.sel.delete(id)});
  const allOn=arr.length&&arr.every(l=>S.sel.has(l.id));$("#allChk").style.cssText=allOn?"background:var(--accent);border-color:var(--accent);color:var(--accent-text)":"";
  renderDetail();
}
let lastDetail=null;
function renderDetail(){
  const d=$("#detail"),l=S.find.find(x=>x.id===S.active);
  if(!l){lastDetail=null;d.innerHTML=`<div class="empty" style="height:100%"><div class="bub">${ic("user")}</div><b>Select a business</b>Details, hours and call buttons show up here.</div>`;hydrateIcons(d);return}
  const sig=JSON.stringify([l,[...S.sel].length]);if(lastDetail&&lastDetail.sig===sig&&d.dataset.id===l.id)return;
  const changed=!lastDetail||lastDetail.id!==l.id;
  if(!changed){const o=$("#dOwner"),nt=$("#dNotes");if(o&&(document.activeElement===o||document.activeElement===nt)){lastDetail={id:l.id,sig};patchDetail(l);return}}
  lastDetail={id:l.id,sig};d.dataset.id=l.id;
  const n=S.sel.size;
  d.innerHTML=`<div class="${changed?"dsw":""}"><div class="dh"><div class="av" style="background:${hue(l.btype)}">${esc(initials(l.name))}</div><div style="min-width:0"><h2>${esc(l.name)}</h2><div class="sub">${esc(l.btype)} · ${esc(l.address)}</div></div>
   <div class="acts"><button class="btn sm" id="dCopy">${ic("copy")}Copy phone</button><button class="btn sm" id="dSite"${l.website===NA?" disabled":""}>${ic("globe")}Website</button></div></div>
  <div class="facts">
   <div class="fact"><div class="k">Phone</div><div class="v">${esc(l.phone)}<span style="font-size:13.5px;font-weight:700;color:#FFD60A">${esc(reviewTxt(l))}</span></div></div>
   <div class="fact"><div class="k">Open now?</div><div class="v">${openPill(l)}<span style="font-size:13.5px;font-weight:500;color:#C8DACF">${esc(hoursTxt(l))}</span></div></div>
   <div class="fact"><div class="k">Owner / contact</div><input class="inp" id="dOwner" value="${esc(l.owner===NA?"":l.owner)}" placeholder="N/A - type a name" maxlength="80"></div>
   <div class="fact"><div class="k">Google rating</div><div class="v">${l.rating===NA?NA:esc(l.rating)+" ★"}<span style="font-size:13.5px;font-weight:500;color:#C8DACF">${l.reviews===NA?"":esc(num(l.reviews))+" reviews"}</span></div></div>
   <div class="fact span"><div class="k">Call notes</div><textarea class="inp" id="dNotes" rows="3" placeholder="What was said, when to call back..." maxlength="2000" style="margin-top:4px;background:var(--bg)">${esc(l.notes)}</textarea></div></div>
  <div style="display:flex;justify-content:flex-end"><button class="btn sm" id="dSave">Save owner &amp; notes</button></div>
  <div class="mark"><div class="t" id="markT">${n?`Mark ${n} selected business${n===1?"":"es"} as`:"Mark this business as"}</div>
   <div class="sb">${ORDER.map(k=>`<button class="st ${ST[k].cls}" data-mark="${k}">${ST[k].label}</button>`).join("")}</div></div></div>`;
  hydrateIcons(d);
}
function patchDetail(l){const n=S.sel.size,t=$("#markT");if(t)t.textContent=n?`Mark ${n} selected business${n===1?"":"es"} as`:"Mark this business as"}
async function saveDetail(silent){
  const l=S.find.find(x=>x.id===S.active),o=$("#dOwner"),nt=$("#dNotes");if(!l||!o||!nt)return;
  const ow=o.value.trim(),no=nt.value.trim();if((ow||NA)===l.owner&&no===l.notes)return;
  try{const r=await api("save_lead",l.id,ow,no);l.owner=r.owner;l.notes=no;lastDetail=null;if(!silent)toast("Saved");renderFind()}catch(e){toast("Couldn't save: "+e.message,{bad:1})}
}
async function markLeads(status,fromBoard){
  let ids=fromBoard||(S.sel.size?[...S.sel]:S.active?[S.active]:[]);
  if(!ids.length)return toast("Click a business first.",{bad:1});
  await saveDetail(true);
  try{await api("mark",ids,status)}catch(e){return toast("Couldn't update: "+e.message,{bad:1})}
  const nodes=ids.map(id=>$(`.li[data-id="${CSS.escape(id)}"]`)).filter(Boolean);
  if(!fromBoard&&!REDUCE)await Promise.all(nodes.map(n=>n.animate([{opacity:1,transform:"none",maxHeight:"120px"},{opacity:0,transform:"translateX(40px) scale(.92)",maxHeight:"0px"}],{duration:300,easing:"cubic-bezier(.4,0,.2,1)",fill:"forwards"}).finished.catch(()=>{})));
  S.sel.clear();const first=S.find.findIndex(l=>ids.includes(l.id));S.find=S.find.filter(l=>!ids.includes(l.id));
  const arr=visibleFind();S.active=arr[Math.min(Math.max(first,0),arr.length-1)]?.id||null;lastDetail=null;
  await reload();
  const n=ids.length;logNote(`${n} marked "${ST[status]?ST[status].label:"Back to call list"}"`);
  toast(status==="none"?`${n} back on the call list`:`${n} moved to Called Leads: ${ST[status].label}`,{action:{label:"Undo",fn:async()=>{try{await api("mark",ids,fromBoard?prevStatus(fromBoard):"none")}catch(e){};await reload()}}});
  if(status==="green")meetingModal(ids);
}
const prevStatus=()=>"none";
/* ---------------- CALLED board ---------------- */
function leadModal(l){
  const close=openModal(`<div class="dh"><div class="av" style="background:${hue(l.btype)}">${esc(initials(l.name))}</div><div style="min-width:0"><h2>${esc(l.name)}</h2><div class="sub">${esc(l.btype)} · ${esc(l.address)}</div></div></div>
   <div class="facts"><div class="fact"><div class="k">Phone</div><div class="v">${esc(l.phone)}<button class="btn sm" data-copy style="margin-left:auto">${ic("copy")}Copy</button></div></div>
   <div class="fact"><div class="k">Open now?</div><div class="v">${openPill(l)}<span style="font-size:13.5px;font-weight:500;color:#C8DACF">${esc(hoursTxt(l))}</span></div></div>
   <div class="fact"><div class="k">Owner / contact</div><input class="inp" id="mOwner" value="${esc(l.owner===NA?"":l.owner)}" placeholder="N/A - type a name" maxlength="80"></div>
   <div class="fact"><div class="k">Last called</div><div class="v">${esc(fmtDate(l.called_at)||NA)}</div></div>
   ${l.status==="green"?`<div class="fact span"><div class="k">Meeting date &amp; time</div><input class="inp" id="mWhen" type="datetime-local" value="${esc((l.meeting_at||"").replace(" ","T"))}"></div>`:""}
   ${l.status!=="none"?creditField("lead",l.called_by):""}
   <div class="fact span"><div class="k">Call notes</div><textarea class="inp" id="mNotes" rows="3" maxlength="2000" style="margin-top:4px;background:var(--bg)" placeholder="What was said, when to call back...">${esc(l.notes)}</textarea></div></div>
   <div class="mark" style="margin-top:6px"><div class="t">Change result</div><div class="sb">${ORDER.map(k=>`<button class="st ${ST[k].cls}${l.status===k?" cur":""}" data-res="${k}">${ST[k].label}</button>`).join("")}</div></div>
   <div style="display:flex;gap:10px;margin-top:18px;flex-wrap:wrap"><button class="btn" data-back>Back to call list</button><button class="btn" data-site${l.website===NA?" disabled":""}>${ic("globe")}Website</button><span style="flex:1"></span><button class="btn" data-x>Close</button><button class="btn pri" data-save>Save</button></div>`,
  (ov,close)=>{
    const save=async()=>{const ow=$("#mOwner",ov).value.trim(),no=$("#mNotes",ov).value.trim();if((ow||NA)!==l.owner||no!==l.notes){try{await api("save_lead",l.id,ow,no)}catch(e){toast("Couldn't save",{bad:1});return false}}const mw=$("#mWhen",ov);if(mw&&mw.value.replace("T"," ")!==(l.meeting_at||"")){try{await api("set_meeting",l.id,mw.value)}catch(e){toast("Couldn't save the meeting time",{bad:1});return false}}return true};
    $("[data-x]",ov).onclick=close;$("[data-copy]",ov).onclick=()=>copyText(l.phone);$("[data-site]",ov).onclick=()=>api("open_site",l.id);
    wireCredit(ov,"lead",l.id,()=>{close();reload()});
    $("[data-save]",ov).onclick=async()=>{if(await save()){close();toast("Saved");reload()}};
    $$("[data-res]",ov).forEach(b=>b.onclick=async()=>{if(await save()){close();await changeStatus([l.id],b.dataset.res,l.status)}});
    $("[data-back]",ov).onclick=async()=>{if(await save()){close();await changeStatus([l.id],"none",l.status)}};
  });
}
async function changeStatus(ids,status,prev){
  try{await api("mark",ids,status)}catch(e){return toast("Couldn't update: "+e.message,{bad:1})}
  await reload();const first=ids[0];
  setTimeout(()=>bump($(`.kc[data-id="${CSS.escape(first)}"]`)),60);
  toast(status==="none"?"Back on the call list":`Moved to ${ST[status].label}`,{action:{label:"Undo",fn:async()=>{try{await api("mark",ids,prev)}catch(e){};await reload()}}});
  if(status==="green")meetingModal(ids);
}
function renderBoard(q){
  const pg=$("#pg-called"),all=S.called.filter(match),types=[...new Map(S.called.map(l=>[l.btype.toLowerCase(),l.btype])).values()].sort((a,b)=>a.localeCompare(b));
  if(S.type!=="all"&&!types.some(t=>t.toLowerCase()===S.type))S.type="all";
  const who=getP("calledWho","all"),grp=getP("calledGroup","type"),srt=getP("calledSort","new"),mid=(S.me&&S.me.id)||"";
  const callers=[...new Map(S.called.filter(l=>l.called_by).map(l=>[l.called_by,l.called_by_name||"Teammate"])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
  const byDay=l=>(l.called_at||"").slice(0,10);
  const cmpS={new:(a,b)=>(b.called_at||"").localeCompare(a.called_at||"")||a.name.localeCompare(b.name),old:(a,b)=>(a.called_at||"~").localeCompare(b.called_at||"~")||a.name.localeCompare(b.name),name:(a,b)=>a.name.localeCompare(b.name)}[srt]||(()=>0);
  const rows=all.filter(l=>(S.type==="all"||l.btype.toLowerCase()===S.type)&&(who==="all"||(who==="me"?l.called_by===mid:who==="none"?!l.called_by:l.called_by===who))).sort(cmpS);
  const gkey=l=>grp==="caller"?(l.called_by||"~none"):grp==="day"?(byDay(l)||"~"):l.btype.toLowerCase();
  const glabel=l=>grp==="caller"?(l.called_by_name||"Caller not recorded"):grp==="day"?(byDay(l)?dayFmt(byDay(l)):"No date"):l.btype;
  const by=k=>rows.filter(l=>l.status===k),cnt=k=>S.called.filter(l=>l.status===k).length;
  const fold=new Set(getP("calledFold",[]));
  const sig=JSON.stringify([rows,S.type,types,who,grp,srt,[...fold]]);if(q&&S.lastSig.board===sig)return;S.lastSig.board=sig;
  const scroll=$$(".col .cb",pg).map(c=>c.scrollTop);
  pg.innerHTML=`<div class="two" style="grid-template-columns:1fr auto;align-items:end;margin-bottom:4px"><div><h3 style="font-size:20px;font-weight:800">Call results</h3><div class="muted" style="font-size:13px;margin-top:2px">Drag a card to another column to change its result, or click a card to edit it. Group and filter by business type, who called, or the day.</div></div>
    <div class="cflt"><select id="cwho" aria-label="Who called"><option value="all">Everyone's calls</option><option value="me"${who==="me"?" selected":""}>My calls</option>${callers.filter(c=>c[0]!==mid).map(c=>`<option value="${esc(c[0])}"${who===c[0]?" selected":""}>${esc(c[1])}'s calls</option>`).join("")}<option value="none"${who==="none"?" selected":""}>Caller not recorded</option></select>
     <select id="cgrp" aria-label="Group cards by"><option value="type"${grp==="type"?" selected":""}>Group: type</option><option value="caller"${grp==="caller"?" selected":""}>Group: caller</option><option value="day"${grp==="day"?" selected":""}>Group: day</option></select>
     <select id="csort" aria-label="Sort cards"><option value="new"${srt==="new"?" selected":""}>Newest calls first</option><option value="old"${srt==="old"?" selected":""}>Oldest calls first</option><option value="name"${srt==="name"?" selected":""}>Business A-Z</option></select>
     <select id="tsel" aria-label="Business type"><option value="all">All business types</option>${types.map(t=>`<option value="${esc(t.toLowerCase())}"${S.type===t.toLowerCase()?" selected":""}>${esc(t)}</option>`).join("")}</select><button class="btn" id="cExport">${ic("down")}Export CSV</button></div></div>
   <div class="cstats">${ORDER.map(k=>`<div class="cstat pop"><div class="ico tone-${ST[k].cls}">${ic(k==="green"?"check":k==="yellow"?"user":k==="orange"?"phone":"bell")}</div><div><div class="n">${num(cnt(k))}</div><div class="t">${ST[k].label}</div></div></div>`).join("")}</div>
   ${S.called.length?`<div class="board">${ORDER.map(k=>{const a=by(k),g0=new Map();a.forEach(l=>{const key=gkey(l);if(!g0.has(key))g0.set(key,{n:glabel(l),a:[]});g0.get(key).a.push(l)});
       const g=new Map([...g0.entries()].sort((x,y)=>grp==="day"?(srt==="old"?x[0].localeCompare(y[0]):y[0].localeCompare(x[0])):x[1].n.localeCompare(y[1].n)));
     return `<div class="col pop" data-col="${k}"><div class="ch"><i style="background:${ST[k].color}"></i>${ST[k].label}<span class="n">${a.length}</span>${g.size>1?(()=>{const allShut=[...g.keys()].every(gk=>fold.has(foldKey(k,grp,gk)));return `<button class="fall${allShut?" all":""}" data-fall="${k}" title="${allShut?"Show every group":"Hide every group"}" aria-label="${allShut?"Show every group in":"Hide every group in"} ${esc(ST[k].label)}">${ic("down")}</button>`})():""}${k==="green"?`<button class="addm" data-addmeet title="Set up a meeting and add it to the Calendar" aria-label="Set up a meeting">${ic("plus")}Set up a meeting</button>`:""}</div><div class="cb">${a.length?[...g.entries()].map(([gk,x])=>{const fk=foldKey(k,grp,gk),shut=fold.has(fk);return `<button class="grp" data-fold="${esc(fk)}" aria-expanded="${!shut}" style="--cc:${ST[k].color}" title="${shut?"Show":"Hide"} ${esc(x.n)}"><i class="ic gc">${svg("down")}</i><span class="gl">${esc(x.n)}</span><span class="gn">${x.a.length}</span></button><div class="gb${shut?" fold":""}"><div>${x.a.map(l=>`<div class="kc ${q?"":"pop"}" draggable="true" data-id="${esc(l.id)}" tabindex="0" style="--cc:${ST[k].color}"><b>${esc(l.name)}</b><div class="m"><span>${esc(l.phone)}</span>${l.owner!==NA?`<span>${esc(l.owner)}</span>`:""}</div>${l.called_by_name?`<div class="cby"><i>${esc(initialsOf(l.called_by_name))}</i>Called by ${esc(l.called_by_name)}</div>`:""}${openPill(l)}<span class="hrs">${esc(l.hours!==NA?(l.hours==="Closed"?"Closed today":l.hours):"")}</span>${k==="green"?`${l.meeting_at?`<button class="mchip" data-meet="${esc(l.id)}" title="Change the meeting time">${ic("cal")}${esc(meetFmt(l.meeting_at))}</button>`:`<button class="mchip setup" data-setup="${esc(l.id)}" title="Adds a meeting for ${esc(l.name)} to the Calendar (next business day, 10 am)">${ic("cal")}Set up meeting</button>`}`:""}<div class="when">${esc(fmtDate(l.called_at))}</div></div>`).join("")}</div></div>`}).join(""):`<div class="muted" style="font-size:13px;padding:14px 10px;text-align:center">Drop a card here</div>`}</div></div>`}).join("")}</div>`
    :`<div class="card empty pop" style="margin-top:6px"><div class="bub">${ic("phone")}</div><b>No called businesses yet</b>Mark a business on Find Leads and it shows up here.</div>`}`;
  hydrateIcons(pg);if(q)quiet(pg);
  $$(".col .cb",pg).forEach((c,i)=>c.scrollTop=scroll[i]||0);
  const ts=$("#tsel");if(ts)ts.onchange=()=>{S.type=ts.value;renderBoard(true)};
  [["cwho","calledWho"],["cgrp","calledGroup"],["csort","calledSort"]].forEach(([id,k])=>{const e=$("#"+id,pg);if(e)e.onchange=()=>{setP(k,e.value);renderBoard(true)}});
  $$("[data-setup]",pg).forEach(b=>{b.onclick=e=>{e.stopPropagation();quickMeeting(b.dataset.setup)};b.draggable=false;b.onmousedown=e=>e.stopPropagation()});
  const ex=$("#cExport");if(ex)ex.onclick=()=>exportCsv(true);
  $$("[data-meet]",pg).forEach(b=>{b.onclick=e=>{e.stopPropagation();meetingModal([b.dataset.meet])};b.draggable=false;b.onmousedown=e=>e.stopPropagation()});
  const am=$("[data-addmeet]",pg);if(am)am.onclick=()=>pickMeetingModal();
  $$("[data-fold]",pg).forEach(b=>{b.onclick=e=>{e.stopPropagation();const open=b.getAttribute("aria-expanded")==="true";setFold([b.dataset.fold],open);
      b.setAttribute("aria-expanded",String(!open));b.title=(open?"Show ":"Hide ")+$(".gl",b).textContent;b.nextElementSibling.classList.toggle("fold",open);syncFall(pg)};
    b.onkeydown=e=>e.stopPropagation()});
  $$("[data-fall]",pg).forEach(b=>b.onclick=e=>{e.stopPropagation();const col=b.closest(".col"),hs=$$("[data-fold]",col),shut=!b.classList.contains("all");
    setFold(hs.map(h=>h.dataset.fold),shut);hs.forEach(h=>{h.setAttribute("aria-expanded",String(!shut));h.nextElementSibling.classList.toggle("fold",shut)});syncFall(pg)});
  $$(".kc",pg).forEach(c=>{
    c.onclick=()=>{const l=S.called.find(x=>x.id===c.dataset.id);l&&leadModal(l)};
    c.onkeydown=e=>{if(e.key==="Enter")c.click()};
    c.ondragstart=e=>{e.dataTransfer.setData("text/plain",c.dataset.id);e.dataTransfer.effectAllowed="move";c.classList.add("drag")};
    c.ondragend=()=>c.classList.remove("drag");
  });
  $$(".col",pg).forEach(col=>{
    col.ondragover=e=>{e.preventDefault();col.classList.add("over")};
    col.ondragleave=e=>{if(!col.contains(e.relatedTarget))col.classList.remove("over")};
    col.ondrop=e=>{e.preventDefault();col.classList.remove("over");const id=e.dataTransfer.getData("text/plain"),l=S.called.find(x=>x.id===id);
      if(l&&l.status!==col.dataset.col)changeStatus([id],col.dataset.col,l.status)};
  });
}
const foldKey=(col,grp,gk)=>col+"|"+grp+"|"+String(gk).slice(0,40);
function setFold(keys,shut){
  const f=getP("calledFold",[]).filter(k=>!keys.includes(k));if(shut)f.push(...keys);
  let out=f.slice(-60);while(out.length&&JSON.stringify(out).length>1900)out=out.slice(1);
  setP("calledFold",out);S.lastSig.board=null;
}
function syncFall(pg){$$("[data-fall]",pg).forEach(b=>{const hs=$$("[data-fold]",b.closest(".col")),all=hs.length&&hs.every(h=>h.getAttribute("aria-expanded")==="false");
  b.classList.toggle("all",all);b.title=all?"Show every group":"Hide every group"})}
/* ---------------- PROFITS ---------------- */
function renderProfits(q){
  const st=S.stats,pg=$("#pg-profits");if(!st||!st.money)return;
  const m=st.money,wk=m.week,mo=m.month,al=m.all,sig=JSON.stringify([S.deals,m]);
  if(q&&S.lastSig.profits===sig)return;S.lastSig.profits=sig;
  const sc=pg.scrollTop,mname=mo.label.split(" ")[0];
  const cards=[
   {c:"s1",tone:"tone-g",ico:"dollar",ib:"#2BB567",lb:"Projected this week",v:wk.projected,dl:`${usd(wk.received)} confirmed · ${usd(wk.upcoming)} not yet`},
   {c:"s2",tone:"tone-y",ico:"cal",ib:"#C9A400",lb:"Made in "+mname,v:mo.made,dl:`of ${usd(mo.total)} scheduled this month`},
   al.unconfirmed>0?{c:"s3",tone:"tone-y",ico:"bell",ib:"#C9A400",lb:"Waiting for confirmation",v:al.unconfirmed,dl:`${num((al.to_confirm||[]).length)} payment${(al.to_confirm||[]).length===1?"":"s"} not confirmed yet`}
    :{c:"s3",tone:"tone-g",ico:"check",ib:"#1FA64A",lb:"On the way",v:al.on_the_way,dl:"Scheduled, not received yet"},
   {c:"s4",tone:"tone-o",ico:"pct",ib:"#E8680C",lb:"Monthly recurring",v:al.mrr,dl:"Billing every month right now"}];
  const KIND={upfront:"Upfront",monthly:"Monthly"};
  const payBtn=p=>p.paid?`<button class="cfm done" data-pay="${p.deal_id}|${esc(p.date)}|${esc(p.kind)}|0" title="Confirmed. Click to undo" aria-label="Payment received from ${esc(p.client)}. Click to undo">${ic("check")}Received</button>`
    :(p.due===undefined?p.date<=m.today:p.due)?`<button class="cfm" data-pay="${p.deal_id}|${esc(p.date)}|${esc(p.kind)}|1" aria-label="Confirm ${usd(p.amount)} from ${esc(p.client)} was received">${ic("check")}Confirm</button>`
    :`<span class="pill unknown">Upcoming</span>`;
  const todo=al.to_confirm||[];
  const plist=wk.payments.length?wk.payments.map(p=>`<div class="prow"><div style="min-width:0;flex:1"><b>${esc(p.client)}</b><span class="sub">${esc(dayFmt(p.date))} · ${KIND[p.kind]||p.kind}</span></div><b class="num">${usd(p.amount)}</b>${payBtn(p)}</div>`).join(""):
    `<div class="empty" style="padding:22px 10px"><div class="bub">${ic("dollar")}</div><b>Nothing due this week</b>Payments from your deals show up here.</div>`;
  const rows=S.deals.map(d=>`<div class="dr" data-id="${d.id}" tabindex="0"><div style="min-width:0"><b>${esc(d.client)}</b>${d.notes?`<span class="sub">${esc(d.notes)}</span>`:""}</div><div>${esc(terms(d))}</div><div>${esc(dayFmt(d.closed_at))}</div><div class="num">${usd(d.collected)}${d.unconfirmed_count?`<span class="sub" style="color:#FFE36B">${num(d.unconfirmed_count)} to confirm</span>`:""}</div><div class="num">${d.remaining===null?"Ongoing":usd(d.remaining)}</div><div>${d.next_date?`<b>${esc(dayFmt(d.next_date))}</b><span class="sub">${usd(d.next_amount)}</span>`:`<span class="muted">All paid</span>`}</div><div><button class="ib" data-edit aria-label="Edit ${esc(d.client)}" tabindex="-1">${ic("edit")}</button></div></div>`).join("");
  pg.innerHTML=`
  <div class="pg-head pop"><div><h3 style="font-size:20px;font-weight:800">Money tracker</h3><div class="muted" style="font-size:13px;margin-top:2px;max-width:640px">Every number here comes from the deals you type in. A payment only counts as made after you press <b>Confirm</b> on it, once the money is really in. Weeks run Monday to Sunday.</div></div><button class="btn pri" data-add>${ic("plus")}Add deal</button></div>
  <div class="stats">${cards.map(c=>`<div class="stat ${c.c} pop"><div class="ico ${c.tone||"tone-g"}"><i class="ic">${svg(c.ico)}</i></div><div class="lb">${c.lb}</div><div class="vl"><small style="font-size:.62em;margin-right:2px;color:#9CF2C3">$</small><span data-n="${c.v}" data-d="${Number.isInteger(c.v)?0:2}">0</span></div><div class="dl">${esc(c.dl)}</div></div>`).join("")}</div>
  <div class="two"><div class="card chart-c pop"><div class="hd"><h3>This week, day by day</h3><span class="muted" style="font-size:12.5px;font-weight:600">${esc(dayFmt(wk.start))} – ${esc(dayFmt(wk.end))} · ${num(wk.closed)} deal${wk.closed===1?"":"s"} closed</span></div>
    ${barChart({labels:wk.days.map(d=>d.label),hi:wk.days.findIndex(d=>d.date===m.today),money:true,future:wk.days.map(d=>d.future),aria:"Money scheduled for each day of this week",series:[{v:wk.days.map(d=>d.amount),c:"b0",name:"Scheduled"}],tips:wk.days.map(d=>`${dayFmt(d.date)}: ${usd(d.amount)}${d.future?" due":d.amount?" received":""}`)})}</div>
   <div class="card types pop"><div class="hd"><h3>Payments this week</h3><span class="muted" style="font-size:12.5px;font-weight:600">${usd(wk.projected)} total</span></div><div class="plist">${plist}</div></div></div>
  ${todo.length?`<div class="card tocf pop"><div class="hd"><div><h3>Waiting for confirmation</h3><div class="muted" style="font-size:12.5px;margin-top:2px">These payment dates have passed. Confirm each one once the money is really in; until then it doesn't count as made.</div></div><span class="pill" style="background:rgba(255,214,10,.16);color:#FFE36B">${usd(al.unconfirmed)}</span></div>
   <div class="plist">${todo.slice().reverse().map(p=>`<div class="prow"><div style="min-width:0;flex:1"><b>${esc(p.client)}</b><span class="sub">${esc(dayFmt(p.date))} · ${KIND[p.kind]||p.kind}</span></div><b class="num">${usd(p.amount)}</b>${payBtn(Object.assign({paid:false,due:true},p))}</div>`).join("")}</div></div>`:""}
  <div class="card pop" style="margin-top:16px;padding:18px 0 10px"><div style="display:flex;justify-content:space-between;align-items:center;padding:0 20px 10px"><h3>Deals</h3><span class="muted" style="font-size:12.5px;font-weight:600">${num(S.deals.length)} total${S.deals.length?" · click a deal to edit it":""}</span></div>
   ${S.deals.length?`<div class="dealtab"><div class="dr h"><div>Client</div><div>Terms</div><div>Closed</div><div>Collected</div><div>Still to come</div><div>Next payment</div><div></div></div>${rows}</div>`:
   `<div class="empty"><div class="bub">${ic("dollar")}</div><b>No deals yet</b>Add a closed deal and your projected profits show up here and on the Dashboard.<button class="btn pri" data-add style="margin-top:8px">${ic("plus")}Add your first deal</button></div>`}</div>`;
  hydrateIcons(pg);pg.scrollTop=sc;
  $$("[data-add]",pg).forEach(b=>b.onclick=()=>dealModal(null));
  wirePay(pg);
  $$(".dr[data-id]",pg).forEach(r=>{r.onclick=()=>{const d=S.deals.find(x=>String(x.id)===r.dataset.id);d&&dealModal(d)};r.onkeydown=e=>{if(e.key==="Enter")r.click()}});
  const fire=()=>$$("[data-n]",pg).forEach(e=>{if(q)e.dataset.q=1;countTo(e,+e.dataset.n,+e.dataset.d,"")});
  if(q){quiet(pg);fire()}else setTimeout(fire,350);
}
/* Confirm payment: a payment only counts as money made once someone presses Confirm on it */
async function confirmPay(id,day,kind,on,btn){
  if(btn){btn.disabled=true}
  try{const r=await api("confirm_payment",+id,day,kind,!!on);
    if(!r||!r.ok){if(btn)btn.disabled=false;return toast((r&&r.error)||"Couldn't save that.",{bad:1})}
    if(btn){btn.classList.add("pulse");const row=btn.closest(".tocf .prow");if(row&&on)row.classList.add("gone")}
    toast(on?"Payment confirmed. It now counts as made.":"Confirmation removed",{action:{label:"Undo",fn:()=>confirmPay(id,day,kind,!on)}});
    logNote((on?"Confirmed":"Un-confirmed")+" a "+kind+" payment ("+dayFmt(day)+")");
    setTimeout(reload,on&&btn?380:0);
  }catch(e){if(btn)btn.disabled=false;toast("Couldn't save: "+e.message,{bad:1})}
}
function wirePay(root){$$("[data-pay]",root).forEach(b=>b.onclick=e=>{e.stopPropagation();const [id,day,kind,on]=b.dataset.pay.split("|");confirmPay(id,day,kind,on==="1",b)})}
function dealModal(d){
  const isNew=!d,t0=isoDay(new Date());d=d||{id:0,client:"",upfront:0,monthly:0,months:0,closed_at:t0,first_bill:"",notes:""};
  const val=v=>v?v:"";
  openModal(`<h2>${isNew?"Add a deal":"Edit deal"}</h2><p class="muted" style="margin:6px 0 0;font-size:13px;line-height:1.5">Type in what the client agreed to pay. Leave the months box empty if the monthly payment has no end date.</p>
   <div class="fg">
    <div style="grid-column:1/3"><label class="l" for="dClient">Client / business</label><input class="inp" id="dClient" maxlength="80" value="${esc(d.client)}" placeholder="e.g. Maple Roofing"></div>
    <div><label class="l" for="dUp">Upfront payment ($)</label><input class="inp" id="dUp" inputmode="decimal" value="${esc(val(d.upfront))}" placeholder="0"></div>
    <div><label class="l" for="dMo">Monthly payment ($)</label><input class="inp" id="dMo" inputmode="decimal" value="${esc(val(d.monthly))}" placeholder="0"></div>
    <div><label class="l" for="dN">Number of months</label><input class="inp" id="dN" inputmode="numeric" value="${esc(val(d.months))}" placeholder="Empty = ongoing"></div>
    <div><label class="l" for="dClosed">Date closed (upfront is paid)</label><input class="inp" id="dClosed" type="date" value="${esc(d.closed_at)}"></div>
    <div><label class="l" for="dFirst">First monthly payment</label><input class="inp" id="dFirst" type="date" value="${esc(d.first_bill||d.closed_at)}"></div>
    <div><label class="l" for="dNotes">Notes (optional)</label><input class="inp" id="dNotes" maxlength="500" value="${esc(d.notes)}" placeholder="e.g. website + hosting"></div>
    ${isNew?"":`<div style="grid-column:1/3">${creditField("deal",null)}</div>`}
   </div>
   <div class="note" id="dHint" style="min-height:20px"></div>
   <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap">${isNew?"":`<button class="btn" data-del style="color:#FF9AA0">${ic("trash")}Delete</button>`}<span style="flex:1"></span><button class="btn" data-x>Cancel</button><button class="btn pri" data-save>Save deal</button></div>`,
  (ov,close)=>{
    if(!isNew){wireCredit(ov,"deal",d.id,()=>{close();reload()});api("get_credit","deal",d.id).then(r=>{const sel=$("#crWho",ov);if(sel&&r&&r.ok){sel.value=r.owner||"";sel.dataset.cur=r.owner||""}}).catch(()=>{})}
    const g=id=>$("#"+id,ov),pn=v=>parseFloat(String(v).replace(/[$,\s]/g,""))||0;
    let touched=!isNew&&!!d.first_bill&&d.first_bill!==d.closed_at;
    const hint=()=>{const up=pn(g("dUp").value),mo=pn(g("dMo").value),n=parseInt(g("dN").value)||0;
      g("dHint").textContent=mo>0&&n>0?`Total over the whole deal: ${usd(up+mo*n)}`:mo>0?`${up>0?usd(up)+" upfront, then ":""}${usd(mo)} every month until it is cancelled`:up>0?`One-time payment of ${usd(up)}`:"Enter an upfront amount, a monthly amount, or both."};
    ["dUp","dMo","dN"].forEach(i=>g(i).oninput=hint);
    g("dFirst").oninput=()=>{touched=true};
    g("dClosed").oninput=()=>{if(!touched)g("dFirst").value=g("dClosed").value};
    hint();
    const save=async()=>{
      const body={id:d.id,client:g("dClient").value,upfront:g("dUp").value,monthly:g("dMo").value,months:g("dN").value,closed_at:g("dClosed").value,first_bill:g("dFirst").value,notes:g("dNotes").value};
      try{const r=await api("save_deal",body);if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1});
        close();toast(isNew?"Deal added":"Deal saved");logNote((isNew?"Added":"Updated")+" deal: "+body.client.trim());await reload()}
      catch(e){toast("Couldn't save: "+e.message,{bad:1})}
    };
    $("[data-save]",ov).onclick=save;$("[data-x]",ov).onclick=close;
    $$("input",ov).forEach(i=>i.onkeydown=e=>{if(e.key==="Enter")save()});
    const del=$("[data-del]",ov);
    if(del){let armed=false,tm;del.onclick=async()=>{
      if(!armed){armed=true;del.style.cssText="background:#D62828;color:#fff";del.innerHTML=ic("trash")+"Click again to delete";tm=setTimeout(()=>{armed=false;del.style.cssText="color:#FF9AA0";del.innerHTML=ic("trash")+"Delete"},3000);return}
      clearTimeout(tm);try{await api("delete_deal",d.id);close();toast("Deal deleted");logNote("Deleted deal: "+d.client);await reload()}catch(e){toast("Couldn't delete: "+e.message,{bad:1})}
    }}
  });
}
/* ---------------- CALENDAR ---------------- */
const CAL_SRC={meeting:{label:"Meetings",color:"#5C9DFF",icon:"users"},payment:{label:"Payments",color:"#FFD60A",icon:"dollar"},closed:{label:"Deals closed",color:"#3DDC84",icon:"trophy"},event:{label:"My events",color:"#B388FF",icon:"star"}};
const EV_COLORS=["#3DDC84","#4DD0E1","#5C9DFF","#B388FF","#FF7EB6","#FF5C5C","#FF9F43","#FFD60A","#C6F04A","#B8C4BC"];
const EV_ICONS=["cal","users","phone","video","coffee","briefcase","dollar","gift","star","flag","heart","bolt","pin","mail","clock","trophy","bell","check"];
const REPEAT_LBL={none:"Doesn't repeat",daily:"Every day",weekly:"Every week",monthly:"Every month",yearly:"Every year"};
const ink=h=>{const n=parseInt(String(h).slice(1),16),r=n>>16,g=(n>>8)&255,b=n&255;return (.299*r+.587*g+.114*b)>150?"#0B1F14":"#FFFFFF"};
const fmtTime=t=>{if(!t)return "";const [h,m]=t.split(":").map(Number);return (h%12||12)+":"+String(m).padStart(2,"0")+" "+(h<12?"AM":"PM")};
const shortTime=t=>{if(!t)return "";const [h,m]=t.split(":").map(Number);return (h%12||12)+(m?":"+String(m).padStart(2,"0"):"")+(h<12?"a":"p")};
const longDay=s=>new Date(s+"T00:00:00").toLocaleDateString("en-US",{weekday:"long",month:"short",day:"numeric"});
const soonDay=s=>{const t=isoDay(new Date()),tm=new Date();tm.setDate(tm.getDate()+1);return s===t?"Today":s===isoDay(tm)?"Tomorrow":new Date(s+"T00:00:00").toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})};
const calStyle=it=>it.src==="event"?{color:it.color,icon:it.icon}:CAL_SRC[it.src];
function calSub(it){
  if(it.src==="meeting")return (it.time?fmtTime(it.time):"Time not set")+" · Meeting"+(it.owner?" with "+it.owner:"");
  if(it.src==="payment")return (it.kind==="upfront"?"Upfront payment":"Monthly payment")+" · "+(it.paid?"Received":(it.due===undefined?it.date<=isoDay(new Date()):it.due)?"Needs confirming":"Due");
  if(it.src==="closed")return "Deal closed";
  return (it.time?fmtTime(it.time):"All day")+(typeOf(it)?" · "+typeOf(it):"")+(it.repeat!=="none"?" · "+REPEAT_LBL[it.repeat]:"")+(it.lead_name?" · "+it.lead_name:"")+(it.assigned_name?" · For "+it.assigned_name:"")+(it.created_name?" · Added by "+it.created_name:"");
}
const calChip=it=>it.src==="payment"?usd(it.amount)+" "+it.title:(it.time?shortTime(it.time)+" ":"")+it.title;
const calIsPast=it=>it.src==="payment"?it.paid:it.date<isoDay(new Date());
function chipHTML(it){const st=calStyle(it);return `<div class="ce${calIsPast(it)?" past":""}" style="background:${esc(st.color)};color:${ink(st.color)}" title="${esc(it.title)}"><i class="ic">${svg(st.icon)}</i><span>${esc(calChip(it))}</span></div>`}
function rowHTML(it){const st=calStyle(it),ev=it.src==="event";
  return `<div class="crow${calIsPast(it)?" past":""}${ev&&it.done?" dn":""}" data-key="${esc(it.key)}" tabindex="0"><span class="cb" style="background:${esc(st.color)};color:${ink(st.color)}"><i class="ic">${svg(st.icon)}</i></span><div class="cm"><b>${esc(it.title)}</b><span class="sub">${esc(calSub(it))}</span></div>${it.src==="payment"?`<b class="num">${usd(it.amount)}</b>${it.paid?`<button class="cdn on" data-pay="${it.deal_id}|${esc(it.date)}|${esc(it.kind)}|0" title="Received. Click to undo" aria-label="Payment received. Click to undo">✓</button>`:(it.due===undefined?it.date<=isoDay(new Date()):it.due)?`<button class="cfm" data-pay="${it.deal_id}|${esc(it.date)}|${esc(it.kind)}|1" aria-label="Confirm this payment was received">Confirm</button>`:""}`:""}${ev&&it.repeat==="none"?`<button class="cdn${it.done?" on":""}" data-done="${it.id}" data-v="${it.done?0:1}" title="${it.done?"Mark as not done":"Mark as done"}" aria-label="${it.done?"Mark as not done":"Mark as done"}">✓</button>`:""}</div>`}
const EV_TYPES={meeting:["Meeting","users","#5C9DFF"],follow_up:["Follow-up","flag","#FF9F43"],call:["Scheduled call","phone","#4DD0E1"],task:["Task","check","#3DDC84"]};
const typeOf=it=>{const e=Object.entries(EV_TYPES).find(([k,v])=>v[1]===it.icon);return e?e[1][0]:""};
let calTok=0;
async function renderCalendar(q){
  const now=new Date(),C=S.cal||(S.cal={y:now.getFullYear(),m:now.getMonth(),sel:isoDay(now),hide:{},data:null});
  const gs=new Date(C.y,C.m,1);gs.setDate(1-((gs.getDay()+6)%7));
  const ge=new Date(gs);ge.setDate(gs.getDate()+41);
  const t0=new Date(now.getFullYear(),now.getMonth(),now.getDate()),t1=new Date(t0);t1.setDate(t0.getDate()+45);
  const my=++calTok;let items,soon;
  try{[items,soon]=await Promise.all([api("get_calendar",isoDay(gs),isoDay(ge)),api("get_calendar",isoDay(t0),isoDay(t1))])}catch(e){return}
  if(my!==calTok||S.page!=="calendar")return;
  C.data={items,soon,gs};drawCalendar(q);
}
const weekStart=iso=>{const d=new Date(iso+"T00:00:00");d.setDate(d.getDate()-((d.getDay()+6)%7));return d};
function drawCalendar(q){
  const C=S.cal,pg=$("#pg-calendar");if(!C||!C.data)return;
  C.view=C.view||"month";
  const sig=JSON.stringify([C.view,C.y,C.m,C.sel,C.hide,C.data.items,C.data.soon,isoDay(new Date())]);
  if(q&&S.lastSig.cal===sig)return;S.lastSig.cal=sig;
  const show=it=>!C.hide[it.src],items=C.data.items.filter(show),soon=C.data.soon.filter(show),gs=C.data.gs,today=isoDay(new Date());
  const by={},K={};items.forEach(it=>{(by[it.date]=by[it.date]||[]).push(it);K[it.key]=it});soon.forEach(it=>K[it.key]=it);
  const sc=pg.scrollTop,sd=new Date(C.sel+"T00:00:00"),ws=weekStart(C.sel),we=new Date(ws);we.setDate(ws.getDate()+6);
  const md=(d,o)=>d.toLocaleDateString("en-US",o);
  const title=C.view==="month"?md(new Date(C.y,C.m,1),{month:"long",year:"numeric"}):C.view==="week"?md(ws,{month:"short",day:"numeric"})+" – "+md(we,{month:"short",day:"numeric",year:"numeric"}):md(sd,{weekday:"long",month:"long",day:"numeric",year:"numeric"});
  const chips=Object.keys(CAL_SRC).map(k=>{const s=CAL_SRC[k];return `<button class="chip${C.hide[k]?" off":" on"}" data-f="${k}" aria-pressed="${!C.hide[k]}"><span class="cdot" style="background:${s.color};color:${ink(s.color)}"><i class="ic">${svg(s.icon)}</i></span>${s.label}</button>`}).join("");
  let main="";
  if(C.view==="month"){
    let cells="";
    for(let i=0;i<42;i++){
      const d=new Date(gs);d.setDate(gs.getDate()+i);const iso=isoDay(d),list=by[iso]||[];
      cells+=`<div class="cc${d.getMonth()!==C.m?" om":""}${iso===today?" td":""}${iso===C.sel?" sel":""}" data-d="${iso}" tabindex="0" role="button" aria-label="${esc(longDay(iso))}, ${list.length} item${list.length===1?"":"s"}"><div class="cn"><span>${d.getDate()}</span></div>${list.slice(0,3).map(chipHTML).join("")}${list.length>3?`<div class="cmore">+${list.length-3}<span class="cmw"> more</span></div>`:""}</div>`;
    }
    main=`<div class="card cal pop"><div class="cal-dow">${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(x=>`<div>${x}</div>`).join("")}</div><div class="cal-grid">${cells}</div></div>`;
  }else if(C.view==="week"){
    let cols="";
    for(let i=0;i<7;i++){const d=new Date(ws);d.setDate(ws.getDate()+i);const iso=isoDay(d);
      cols+=`<div class="wcol${iso===today?" td":""}${iso===C.sel?" sel":""}" data-d="${iso}"><div class="wh" data-wd="${iso}" title="Open this day"><span>${md(d,{weekday:"short"})}</span><b>${d.getDate()}</b></div><div class="wl">${(by[iso]||[]).map(rowHTML).join("")||`<div class="muted wn">Nothing</div>`}</div><button class="btn sm" data-addd="${iso}">+ Add</button></div>`}
    main=`<div class="card wk pop"><div class="wk-grid">${cols}</div></div>`;
  }else{
    const list=by[C.sel]||[];
    main=`<div class="card dy pop">${list.length?list.map(it=>`<div class="dyr"><span class="dt">${it.time?fmtTime(it.time):"All day"}</span>${rowHTML(it)}</div>`).join(""):`<div class="muted" style="padding:30px 6px;font-size:14px">Nothing on this day yet. Press Add event to schedule a meeting, follow-up or call.</div>`}</div>`;
  }
  const dayItems=by[C.sel]||[];let last="";
  const up=soon.slice(0,30).map(it=>{const h=it.date!==last?(last=it.date,`<div class="cdh">${esc(soonDay(it.date))}</div>`):"";return h+rowHTML(it)}).join("");
  pg.innerHTML=`
  <div class="cal-head pop"><div class="cal-nav"><button class="ib" data-cp aria-label="Previous">${ic("prev")}</button><h3 class="cal-title">${esc(title)}</h3><button class="ib" data-cn aria-label="Next">${ic("next")}</button><button class="chip" data-ct>Today</button></div>
   <div class="cal-views">${[["month","Month"],["week","Week"],["day","Day"]].map(([k,l])=>`<button class="chip${C.view===k?" on":""}" data-view="${k}">${l}</button>`).join("")}</div>
   <div class="cal-filters">${chips}</div><button class="btn pri" data-addev>${ic("plus")}Add event</button></div>
  <div class="cal-wrap v-${C.view}">${main}
   <div class="cside">${C.view==="month"?`<div class="card pop"><div class="hd"><h3>${esc(longDay(C.sel))}</h3><button class="btn sm" data-addday>${ic("plus")}Add</button></div>
     ${dayItems.length?dayItems.map(rowHTML).join(""):`<div class="muted" style="padding:14px 4px;font-size:13.5px">Nothing on this day. Meetings, payments and your own events show up here.</div>`}</div>`:""}
    <div class="card pop"><div class="hd"><h3>Coming up</h3><span class="muted" style="font-size:12.5px;font-weight:600">next 45 days</span></div>
     <div class="cscroll">${up||`<div class="muted" style="padding:14px 4px;font-size:13.5px">Nothing coming up. Add an event, or set a date when you mark a lead "Meeting set up".</div>`}</div></div></div></div>`;
  hydrateIcons(pg);pg.scrollTop=sc;if(q)quiet(pg);
  const goSel=iso=>{const d=new Date(iso+"T00:00:00");C.sel=iso;C.y=d.getFullYear();C.m=d.getMonth()};
  const step=n=>{
    if(C.view==="month"){const d=new Date(C.y,C.m+n,1),t=new Date();C.y=d.getFullYear();C.m=d.getMonth();C.sel=(t.getFullYear()===C.y&&t.getMonth()===C.m)?isoDay(t):isoDay(d)}
    else{const d=new Date(C.sel+"T00:00:00");d.setDate(d.getDate()+n*(C.view==="week"?7:1));goSel(isoDay(d))}
    renderCalendar(true)};
  $("[data-cp]",pg).onclick=()=>step(-1);$("[data-cn]",pg).onclick=()=>step(1);
  $("[data-ct]",pg).onclick=()=>{goSel(isoDay(new Date()));renderCalendar(true)};
  $$("[data-view]",pg).forEach(b=>b.onclick=()=>{C.view=b.dataset.view;goSel(C.sel);renderCalendar(true)});
  $$("[data-f]",pg).forEach(b=>b.onclick=()=>{C.hide[b.dataset.f]=!C.hide[b.dataset.f];drawCalendar(true)});
  $("[data-addev]",pg).onclick=()=>eventModal(null,C.sel);const ad=$("[data-addday]",pg);ad&&(ad.onclick=()=>eventModal(null,C.sel));
  $$("[data-addd]",pg).forEach(b=>b.onclick=()=>eventModal(null,b.dataset.addd));
  $$("[data-wd]",pg).forEach(h=>h.onclick=()=>{goSel(h.dataset.wd);C.view="day";renderCalendar(true)});
  $$(".cc",pg).forEach(c=>{c.onclick=()=>{C.sel=c.dataset.d;drawCalendar(true)};c.ondblclick=()=>eventModal(null,c.dataset.d);c.onkeydown=e=>{if(e.key==="Enter"){C.sel=c.dataset.d;drawCalendar(true)}}});
  $$(".crow",pg).forEach(r=>{r.onclick=()=>{const it=K[r.dataset.key];it&&calOpen(it)};r.onkeydown=e=>{if(e.key==="Enter")r.click()}});
  wirePay(pg);
  $$("[data-done]",pg).forEach(b=>b.onclick=async e=>{e.stopPropagation();const r=await api("set_event_done",+b.dataset.done,b.dataset.v==="1");if(r.ok){toast(b.dataset.v==="1"?"Marked done":"Marked not done");await reload()}});
}
function calOpen(it){
  if(it.src==="event")return eventModal(it);
  if(it.src==="meeting"){const l=S.called.find(x=>x.id===it.lead_id);return l?leadModal(l):toast("Couldn't find that business.",{bad:1})}
  const d=S.deals.find(x=>x.id===it.deal_id);if(d)dealModal(d);else go("profits");
}
const meetFmt=w=>{const d=new Date(String(w).replace(" ","T"));return isNaN(d)?w:d.toLocaleDateString("en-US",{month:"short",day:"numeric"})+" · "+d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})};
function pickMeetingModal(){
  const list=[...S.called].sort((a,b)=>((a.status==="green"&&a.meeting_at?1:0)-(b.status==="green"&&b.meeting_at?1:0))||a.name.localeCompare(b.name));
  if(!list.length)return toast("Mark a business as called first, then add its meeting.",{bad:1});
  openModal(`<h2>Add a meeting</h2><p class="muted" style="margin:6px 0 14px;font-size:13.5px;line-height:1.5">Pick the business. It moves to "Meeting set up" and the meeting appears on the Calendar.</p>
   <label class="l" for="pmBiz">Business</label><input class="inp" id="pmBiz" list="pmList" placeholder="Start typing a business name" style="width:100%" autocomplete="off">
   <datalist id="pmList">${list.map(l=>`<option value="${esc(l.name)}${l.phone?" · "+esc(l.phone):""}">`).join("")}</datalist>
   <div style="display:flex;gap:10px;margin-top:20px;justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn pri" data-next>Next: pick the time</button></div>`,
  (ov,close)=>{
    $("[data-x]",ov).onclick=close;
    const next=()=>{const v=$("#pmBiz",ov).value.trim().toLowerCase();
      const l=list.find(x=>(x.name+(x.phone?" · "+x.phone:"")).toLowerCase()===v)||list.filter(x=>x.name.toLowerCase().includes(v)).length===1&&list.find(x=>x.name.toLowerCase().includes(v));
      if(!l)return toast("Pick a business from the list.",{bad:1});
      close();setTimeout(()=>meetingModal([l.id],true),320)};
    $("[data-next]",ov).onclick=next;$("#pmBiz",ov).onkeydown=e=>{if(e.key==="Enter")next()};
  });
}

/* ---------- credit: who a lead, meeting or deal counts for ---------- */
function teamList(){const m=new Map();(S.people||[]).forEach(p=>{if(p.active!==false)m.set(p.id,p.display_name||p.username||"Teammate")});(B.data&&B.data.people||[]).forEach(p=>m.set(p.id,p.name));if(S.me)m.set(S.me.id,S.me.display_name);return [...m.entries()].sort((a,b)=>a[1].localeCompare(b[1]))}
function creditField(kind,cur){
  return `<div class="fact span crf"><div class="k">Credited to</div><div class="v" style="gap:8px"><select id="crWho" data-cur="${esc(cur||"")}" style="flex:1;min-width:160px;height:38px" aria-label="Who this counts for">${cur?"":`<option value="">${kind==="deal"?"Loading...":"Not recorded"}</option>`}${teamList().map(([id,n])=>`<option value="${esc(id)}"${id===cur?" selected":""}>${esc(n)}${S.me&&id===S.me.id?" (me)":""}</option>`).join("")}</select><button type="button" class="btn sm" id="crMe">That's mine</button></div>
   <div class="note" style="margin-top:6px">${kind==="deal"?"Who this deal's money counts for on the leaderboard.":"Who booked this one. Booked it for a teammate? Pick them, and the meeting counts for them."} The team sees every change in Activity.</div></div>`;
}
function wireCredit(ov,kind,id,after){
  const sel=$("#crWho",ov);if(!sel)return;
  const save=async to=>{if(!to||to===sel.dataset.cur)return;const r=await api("set_credit",kind,id,to).catch(e=>({ok:false,error:e.message}));
    if(!r.ok){sel.value=sel.dataset.cur;return toast(r.error||"Couldn't change it.",{bad:1,ms:6000})}
    sel.dataset.cur=to;B.at=0;const n=(teamList().find(x=>x[0]===to)||[0,"them"])[1];toast(S.me&&to===S.me.id?"It now counts for you":"It now counts for "+n);logNote("Credit moved to "+n);};
  sel.onchange=()=>save(sel.value);
  const me=$("#crMe",ov);if(me){me.style.display=S.me&&sel.dataset.cur===S.me.id?"none":"";me.onclick=()=>{sel.value=S.me.id;save(S.me.id).then(()=>{me.style.display="none"})}}
}
/* ---------- one bar chart for the whole app (dashboard, profits, team) ---------- */
function barChart(o){
  const n=o.labels.length,series=o.series,mx=Math.max(1,...series.flatMap(s=>s.v)),fmt=o.fmt||num,few=n<=8;
  const top=v=>o.money?usd(v):num(v),axis=[mx,mx/2,0].map(v=>o.money?usd(Math.round(v)):num(Math.round(v)));
  return `<div class="bch${o.cls?" "+o.cls:""}${o.still?" in":""}" style="--n:${n};height:${o.h||250}px" role="img" aria-label="${esc(o.aria||"")}"><div class="ax">${axis.map(a=>`<span>${a}</span>`).join("")}</div>
   ${o.labels.map((l,i)=>`<div class="dcol${i===o.hi?" td":""}${o.future&&o.future[i]?" fut":""}"><div class="plot">${series.map((s,k)=>{const v=s.v[i]||0,h=Math.round(100*v/mx);return `<div class="b ${s.c||"b0"}" style="--i:${i};height:${v?Math.max(h,3):0}%">${v&&few?`<span>${top(v)}</span>`:""}</div>`}).join("")}</div>
    <div class="dl">${esc(l)}</div><div class="tip">${esc(o.tips?o.tips[i]:series.map(s=>(s.name?s.name+": ":"")+top(s.v[i]||0)).join(" · "))}</div></div>`).join("")}</div>`;
}
function nextBizSlot(){const d=new Date();do{d.setDate(d.getDate()+1)}while(d.getDay()===0||d.getDay()===6);return isoDay(d)+" 10:00"}
async function quickMeeting(id){
  const l=S.called.find(x=>x.id===id);if(!l)return;
  const when=nextBizSlot();
  try{const r=await api("set_meeting",id,when);if(!r.ok)return toast(r.error||"Couldn't add the meeting.",{bad:1});
    toast("Meeting with "+l.name+" added: "+meetFmt(when),{action:{label:"Change time",fn:()=>meetingModal([id])},ms:7000});
    logNote("Meeting set: "+l.name+" · "+when);await reload()}catch(e){toast("Couldn't add the meeting.",{bad:1})}
}
function meetingModal(ids,promote){
  const ls=ids.map(id=>S.called.find(x=>x.id===id)).filter(Boolean),l=ls[0];if(!l)return;
  const tm=new Date();tm.setDate(tm.getDate()+1);
  const val=(l.meeting_at||"").replace(" ","T")||isoDay(tm)+"T10:00";
  openModal(`<h2>When is the meeting?</h2><p class="muted" style="margin:6px 0 14px;font-size:13.5px;line-height:1.5">${ls.length>1?esc(ls.length+" businesses were"):"<b>"+esc(l.name)+"</b> was"} marked "Meeting set up". Pick the date and time so it shows on the Calendar.</p>
   <label class="l" for="mtWhen">Meeting date &amp; time</label><input class="inp" id="mtWhen" type="datetime-local" value="${esc(val)}" style="width:100%">
   <div class="evt" style="margin-top:10px">${[["Today 3 pm",0,"15:00"],["Tomorrow 10 am",1,"10:00"],["In 2 days",2,"10:00"],["Next week",7,"10:00"]].map(([t,n,h])=>`<button type="button" class="chip" data-q="${n}|${h}">${t}</button>`).join("")}</div>
   <div style="display:flex;gap:10px;margin-top:20px;justify-content:flex-end"><button class="btn" data-x>${promote?"Cancel":"Skip for now"}</button><button class="btn pri" data-save>Add to calendar</button></div>`,
  (ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $$("[data-q]",ov).forEach(b=>b.onclick=()=>{const [n,h]=b.dataset.q.split("|"),d=new Date();d.setDate(d.getDate()+(+n));$("#mtWhen",ov).value=isoDay(d)+"T"+h});
    const save=async()=>{const v=$("#mtWhen",ov).value;if(!v)return toast("Pick a date and time, or press Skip.",{bad:1});
      try{if(promote)await api("mark",ls.map(x=>x.id),"green");for(const x of ls){const r=await api("set_meeting",x.id,v);if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1})}
        close();toast("Meeting added to the Calendar");logNote("Meeting set: "+l.name+" · "+v.replace("T"," "));await reload()}catch(e){toast("Couldn't save: "+e.message,{bad:1})}};
    $("[data-save]",ov).onclick=save;$("#mtWhen",ov).onkeydown=e=>{if(e.key==="Enter")save()};
  });
}
function eventModal(it,day){
  const isNew=!it,d=it?{id:it.id,title:it.title,date:it.start,time:it.time,color:it.color,icon:it.icon,repeat:it.repeat,until:it.until,notes:it.notes,lead_id:it.lead_id,assigned_to:it.assigned_to||"",created_name:it.created_name||""}:
    {id:0,title:"",date:day||isoDay(new Date()),time:"",color:EV_COLORS[3],icon:"star",repeat:"none",until:"",notes:"",lead_id:"",assigned_to:(S.me&&S.me.id)||"",created_name:""};
  const leads=[...S.called].sort((a,b)=>((b.status==="green")-(a.status==="green"))||a.name.localeCompare(b.name));
  openModal(`<h2>${isNew?"Add an event":"Edit event"}</h2>
   <div class="fg">
    <div style="grid-column:1/3"><label class="l">Type</label><div class="evt" id="evType">${Object.keys(EV_TYPES).map(k=>`<button type="button" class="chip" data-t="${k}">${EV_TYPES[k][0]}</button>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l" for="evTitle">Title</label><input class="inp" id="evTitle" maxlength="80" value="${esc(d.title)}" placeholder="e.g. Call back Maple Roofing"></div>
    <div><label class="l" for="evDate">Date</label><input class="inp" id="evDate" type="date" value="${esc(d.date)}"></div>
    <div><label class="l" for="evTime">Time (empty = all day)</label><input class="inp" id="evTime" type="time" value="${esc(d.time)}"></div>
    <div><label class="l" for="evRep">Repeats</label><select id="evRep" style="width:100%;height:40px">${Object.keys(REPEAT_LBL).map(k=>`<option value="${k}"${d.repeat===k?" selected":""}>${REPEAT_LBL[k]}</option>`).join("")}</select></div>
    <div><label class="l" for="evUntil">Repeat until (optional)</label><input class="inp" id="evUntil" type="date" value="${esc(d.until)}"></div>
    <div style="grid-column:1/3"><label class="l">Color</label><div class="evc" id="evCol">${EV_COLORS.map(c=>`<button type="button" data-c="${c}" style="background:${c}" aria-label="Color ${c}"></button>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l">Symbol</label><div class="evi" id="evIco">${EV_ICONS.map(n=>`<button type="button" data-i="${n}" aria-label="Symbol ${n}">${ic(n)}</button>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l" for="evLead">Linked business (optional)</label><select id="evLead" style="width:100%;height:40px"><option value="">None</option>${leads.map(l=>`<option value="${esc(l.id)}"${d.lead_id===l.id?" selected":""}>${esc(l.name)}${l.status==="green"?" (meeting set up)":""}</option>`).join("")}</select></div>
    <div style="grid-column:1/3"><label class="l" for="evWho">Assigned to</label><select id="evWho" style="width:100%;height:40px"><option value="">Nobody in particular</option>${(S.people||[]).filter(p=>p.active).map(p=>`<option value="${esc(p.id)}"${d.assigned_to===p.id?" selected":""}>${esc(p.display_name)}${S.me&&S.me.id===p.id?" (you)":""}</option>`).join("")}</select>${d.created_name?`<div class="note" style="margin:6px 0 0 4px">Added by ${esc(d.created_name)}</div>`:""}</div>
    <div style="grid-column:1/3"><label class="l" for="evNotes">Notes (optional)</label><input class="inp" id="evNotes" maxlength="500" value="${esc(d.notes)}" placeholder="Anything to remember"></div>
   </div>
   <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap"><span class="note">How it looks:</span><div class="ce" id="evPrev" style="height:28px;font-size:13px"></div><span class="note" id="evRepNote"></span></div>
   <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">${isNew?"":`<button class="btn" data-del style="color:#FF9AA0">${ic("trash")}Delete</button>`}<span style="flex:1"></span><button class="btn" data-x>Cancel</button><button class="btn pri" data-save>Save event</button></div>`,
  (ov,close)=>{
    const g=id=>$("#"+id,ov);let col=d.color,ico=d.icon;
    const paint=()=>{
      $$("#evCol button",ov).forEach(b=>b.classList.toggle("on",b.dataset.c===col));
      $$("#evIco button",ov).forEach(b=>{const on=b.dataset.i===ico;b.style.background=on?col:"";b.style.color=on?ink(col):"";b.style.borderColor=on?col:""});
      const p=g("evPrev");p.style.background=col;p.style.color=ink(col);p.innerHTML=`<i class="ic">${svg(ico)}</i><span>${esc((g("evTime").value?shortTime(g("evTime").value)+" ":"")+(g("evTitle").value.trim()||"Your event"))}</span>`;
      g("evRepNote").textContent=!isNew&&g("evRep").value!=="none"?"Changes apply to every repeat.":"";
    };
    $$("#evType button",ov).forEach(b=>b.onclick=()=>{const t=EV_TYPES[b.dataset.t];ico=t[1];col=t[2];$$("#evType button",ov).forEach(x=>x.classList.toggle("on",x===b));paint()});
    $$("#evType button",ov).forEach(b=>b.classList.toggle("on",EV_TYPES[b.dataset.t][1]===ico));
    $$("#evCol button",ov).forEach(b=>b.onclick=()=>{col=b.dataset.c;paint()});
    $$("#evIco button",ov).forEach(b=>b.onclick=()=>{ico=b.dataset.i;paint()});
    ["evTitle","evTime","evRep"].forEach(i=>{g(i).oninput=paint;g(i).onchange=paint});paint();
    const save=async()=>{
      const body={id:d.id,title:g("evTitle").value,date:g("evDate").value,time:g("evTime").value,repeat:g("evRep").value,until:g("evUntil").value,color:col,icon:ico,notes:g("evNotes").value,lead_id:g("evLead").value,assigned_to:g("evWho").value};
      try{const r=await api("save_event",body);if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1});
        close();toast(isNew?"Event added":"Event saved");if(body.date){const dt=new Date(body.date+"T00:00:00");if(!isNaN(dt)&&S.cal){S.cal.y=dt.getFullYear();S.cal.m=dt.getMonth();S.cal.sel=body.date}}await reload()}
      catch(e){toast("Couldn't save: "+e.message,{bad:1})}
    };
    $("[data-save]",ov).onclick=save;$("[data-x]",ov).onclick=close;
    $$("input",ov).forEach(i=>i.onkeydown=e=>{if(e.key==="Enter")save()});
    const del=$("[data-del]",ov);
    if(del){let armed=false,tm;del.onclick=async()=>{
      if(!armed){armed=true;del.style.cssText="background:#D62828;color:#fff";del.innerHTML=ic("trash")+(d.repeat!=="none"?"Delete ALL repeats - click again":"Click again to delete");tm=setTimeout(()=>{armed=false;del.style.cssText="color:#FF9AA0";del.innerHTML=ic("trash")+"Delete"},3500);return}
      clearTimeout(tm);try{await api("delete_event",d.id);close();toast("Event deleted");await reload()}catch(e){toast("Couldn't delete: "+e.message,{bad:1})}
    }}
  });
}
/* ---------------- preferences, sanitiser ---------------- */
const getP=(k,d)=>(S.prefs&&S.prefs[k]!==undefined)?S.prefs[k]:d;
const setP=(k,v)=>{(S.prefs=S.prefs||{})[k]=v;api("set_pref",k,v).catch(()=>{})};
const SAN_TAGS=new Set(["P","DIV","BR","B","STRONG","I","EM","U","S","STRIKE","DEL","SPAN","FONT","UL","OL","LI","H1","H2","H3","BLOCKQUOTE","A","HR","SUB","SUP","MARK"]);
const SAN_DROP=new Set(["SCRIPT","STYLE","IFRAME","OBJECT","EMBED","SVG","MATH","HEAD","TITLE","META","LINK","NOSCRIPT","TEMPLATE"]);
const SAN_STYLE=new Set(["color","background-color","font-size","font-family","font-weight","font-style","text-decoration","text-align","line-height","margin-left","text-indent"]);
function cleanStyle(s){
  const out=[];String(s||"").split(";").forEach(p=>{const i=p.indexOf(":");if(i<1)return;const k=p.slice(0,i).trim().toLowerCase(),v=p.slice(i+1).trim();
    if(SAN_STYLE.has(k)&&v.length<120&&!/url\(|expression|javascript|@import|[<>{}]/i.test(v))out.push(k+":"+v)});
  return out.join(";");
}
function sanHTML(html){
  const doc=new DOMParser().parseFromString("<body>"+String(html||"")+"</body>","text/html");
  const walk=(src,dst)=>{
    for(const n of Array.from(src.childNodes)){
      if(n.nodeType===3){dst.appendChild(document.createTextNode(n.nodeValue));continue}
      if(n.nodeType!==1)continue;
      const tag=n.tagName;
      if(SAN_DROP.has(tag))continue;
      if(!SAN_TAGS.has(tag)){walk(n,dst);continue}
      const el=document.createElement(tag.toLowerCase());
      const st=cleanStyle(n.getAttribute("style"));if(st)el.setAttribute("style",st);
      if(tag==="FONT"){const sz=n.getAttribute("size"),co=n.getAttribute("color");if(/^[1-7]$/.test(sz||""))el.setAttribute("size",sz);if(/^#?[0-9a-f]{3,8}$|^[a-z]{3,20}$/i.test(co||""))el.setAttribute("color",co)}
      if(tag==="A"){const h=(n.getAttribute("href")||"").trim();if(/^(https?:\/\/|mailto:|tel:)/i.test(h)){el.setAttribute("href",h);el.setAttribute("target","_blank");el.setAttribute("rel","noopener noreferrer")}}
      if(tag!=="BR"&&tag!=="HR")walk(n,el);
      dst.appendChild(el);
    }
  };
  const box=document.createElement("div");walk(doc.body,box);return box.innerHTML;
}
const plainOf=h=>{const d=document.createElement("div");d.innerHTML=sanHTML(h);return d.textContent||""};

/* ---------------- notes + scripts ---------------- */
const N={list:[],cur:null,dirty:false,kind:"all",q:"",folder:"",read:false,saving:false,sel:null,t:0};
const FONTS=["Default","Arial","Georgia","Times New Roman","Verdana","Courier New","Trebuchet MS","Segoe UI"];
const SIZES=[10,12,14,16,18,20,24,28,32,40,48];
const zoomOf=()=>Math.max(60,Math.min(260,getP("readZoom",100)));
async function loadNotes(){try{N.list=await api("get_notes")||[];S.nlist=N.list}catch(e){}}
function noteAge(n){return n.unsynced?"Saving…":""}
function drawNoteList(){
  const box=$("#ntItems");if(!box)return;
  const q=N.q.trim().toLowerCase();
  let rows=N.list.filter(n=>(N.kind==="all"||n.kind===N.kind)&&(!N.folder||n.folder===N.folder)&&(!q||n.title.toLowerCase().includes(q)||(n.kind==="script"?plainOf(n.body):n.body).toLowerCase().includes(q)));
  const folders=[...new Set(N.list.filter(n=>n.folder).map(n=>n.folder))].sort();
  const fs=$("#ntFolder");if(fs){const cur=N.folder;fs.innerHTML=`<option value="">All folders</option>`+folders.map(f=>`<option${f===cur?" selected":""}>${esc(f)}</option>`).join("");fs.style.display=folders.length?"":"none"}
  const sec=(label,list)=>list.length?`<div class="nt-sec">${label}</div>`+list.map(n=>`<button class="nt-it${N.cur&&N.cur.id===n.id?" on":""}" data-id="${n.id}"><b>${esc(n.title)}</b><small><span class="tag ${n.kind==="script"?"scr":""}">${n.kind==="script"?"Script":"Note"}</span>${n.scope==="shared"?`<span class="tag team">Team · ${esc(n.owner)}</span>`:`<span class="tag me">Only me</span>`}${n.folder?`<span>${esc(n.folder)}</span>`:""}</small></button>`).join(""):"";
  const mine=rows.filter(n=>n.scope!=="shared"),team=rows.filter(n=>n.scope==="shared");
  box.innerHTML=sec("My private notes &amp; scripts",mine)+sec("Shared with the team",team)||`<div class="muted" style="padding:18px 8px;font-size:13.5px;line-height:1.5">${q?"Nothing matches your search.":"Nothing here yet. Press <b>+ Script</b> to write a call script or <b>+ Note</b> for a quick note."}</div>`;
  $$(".nt-it",box).forEach(b=>b.onclick=()=>openNote(+b.dataset.id));
}
async function renderNotes(soft){
  await loadNotes();
  const pg=$("#pg-notes");
  if(!pg.dataset.built){
    pg.dataset.built=1;
    pg.innerHTML=`<div class="nt"><div class="card nt-list"><div class="nt-top">
      <input class="inp" id="ntQ" placeholder="Search notes and scripts" aria-label="Search notes" autocomplete="off">
      <div class="nt-new"><button class="btn sm pri" id="ntNewScript">${ic("plus")}Script</button><button class="btn sm" id="ntNewNote">${ic("plus")}Note</button></div>
      <div class="nt-chips"><button class="chip on" data-nf="all">All</button><button class="chip" data-nf="script">Scripts</button><button class="chip" data-nf="note">Notes</button></div>
      <select id="ntFolder" aria-label="Folder" style="display:none"></select></div><div class="nt-items" id="ntItems"></div></div>
      <div class="card nt-ed" id="ntEd"></div></div>`;
    hydrateIcons(pg);
    $("#ntQ").oninput=e=>{N.q=e.target.value;drawNoteList()};
    $$("[data-nf]",pg).forEach(b=>b.onclick=()=>{N.kind=b.dataset.nf;$$("[data-nf]",pg).forEach(x=>x.classList.toggle("on",x===b));drawNoteList()});
    $("#ntFolder").onchange=e=>{N.folder=e.target.value;drawNoteList()};
    $("#ntNewScript").onclick=()=>newNote("script");$("#ntNewNote").onclick=()=>newNote("note");
  }
  drawNoteList();
  if(N.cur){
    const fresh=N.list.find(n=>n.id===N.cur.id);
    if(!fresh){N.cur=null;N.dirty=false;showEmptyEd()}
    else if(soft){refreshOpen(fresh)}
  }
  if(!N.cur&&!soft){const want=getP("noteId",0),first=N.list.find(n=>n.id===want)||N.list[0];first?openNote(first.id):showEmptyEd()}
  else if(!N.cur)showEmptyEd();
  drawDock(true);
}
function showEmptyEd(){const e=$("#ntEd");if(e)e.innerHTML=`<div class="nt-empty"><div><b style="font-size:18px;color:var(--text)">Notes &amp; call scripts</b><br>Press <b>+ Script</b> to write a call script you can keep open next to your phone numbers.<br>Notes and scripts can be private to you or shared with the whole team.</div></div>`}
async function newNote(kind){
  await flushNote();
  const r=await api("save_note",{kind,scope:"personal",title:kind==="script"?"New script":"New note",body:""});
  if(!r.ok)return toast(r.error||"Couldn't create it.",{bad:1});
  await loadNotes();drawNoteList();await openNote(r.id);const t=$("#edTitle");t&&(t.focus(),t.select());
}
function savedState(txt,bad){const s=$("#edSave");if(s){s.textContent=txt;s.classList.toggle("bad",!!bad)}}
async function openNote(id){
  await flushNote();
  const n=N.list.find(x=>x.id===id);if(!n)return;
  N.cur=Object.assign({},n);N.serverBody=n.body;N.serverTitle=n.title;N.dirty=false;N.read=false;setP("noteId",id);drawNoteList();
  const ed=$("#ntEd"),isS=n.kind==="script",canDel=n.mine||(n.scope==="shared"&&S.me&&S.me.role==="admin"),ownerOK=n.mine;
  ed.innerHTML=`<div class="ed-head"><input class="ed-title" id="edTitle" maxlength="120" value="${esc(n.title)}" aria-label="Title" placeholder="Title">
    <div class="seg" id="edScope" title="${ownerOK?"Who can see this":"Only the owner can change this"}"><button data-s="personal"${ownerOK?"":" disabled"}>Only me</button><button data-s="shared"${ownerOK?"":" disabled"}>Whole team</button></div></div>
   <div class="ed-meta"><span>${n.scope==="shared"?"Shared · owner "+esc(n.owner):"Private to you"}</span><input class="inp" id="edFolder" maxlength="60" placeholder="Folder (optional)" value="${esc(n.folder)}" aria-label="Folder"><span class="sv" id="edSave">Saved</span><span class="sp"></span>
    ${isS?`<button class="btn sm" id="edDock">${ic("pin")}Show beside my leads</button><button class="btn sm" id="edRead">Reading mode</button><button class="btn sm" id="edMinus" title="Smaller text">A−</button><button class="btn sm" id="edPlus" title="Bigger text">A+</button>`:""}
    <button class="btn sm" id="edFocus">Focus</button>${canDel?`<button class="btn sm" id="edDel" style="color:#FF9AA0">${ic("trash")}Delete</button>`:""}</div>
   ${isS?toolbarHTML():""}
   <div class="lnkbar" id="lnkBar"><input class="inp" id="lnkUrl" placeholder="https://…" aria-label="Link address"><button class="btn sm pri" id="lnkOk">Apply</button><button class="btn sm" id="lnkNo">Cancel</button></div>
   ${isS?`<div class="paper" id="edPaper"><div class="rte" id="edBody" contenteditable="true" spellcheck="true" role="textbox" aria-multiline="true" aria-label="Script"></div></div>`:`<textarea class="ntxt" id="edBody" spellcheck="true" aria-label="Note" placeholder="Start typing. It saves by itself."></textarea>`}`;
  hydrateIcons(ed);
  const body=$("#edBody");
  if(isS){body.innerHTML=sanHTML(n.body);body.style.zoom=zoomOf()/100;wireEditor(body)}else{body.value=n.body}
  $$("#edScope button",ed).forEach(b=>{b.classList.toggle("on",b.dataset.s===n.scope);b.onclick=()=>{if(b.disabled||N.cur.scope===b.dataset.s)return;N.cur.scope=b.dataset.s;$$("#edScope button",ed).forEach(x=>x.classList.toggle("on",x===b));
    if(b.dataset.s==="shared")toast("This now shows for everyone on the team.");touch(true)}});
  $("#edTitle").oninput=()=>{N.cur.title=$("#edTitle").value;touch()};
  $("#edFolder").oninput=()=>{N.cur.folder=$("#edFolder").value;touch()};
  body.addEventListener("input",()=>{N.cur.body=isS?body.innerHTML:body.value;touch()});
  $("#edFocus").onclick=()=>toggleFocus();
  const del=$("#edDel");
  if(del){let armed=false,tm;del.onclick=async()=>{
    if(!armed){armed=true;del.style.background="#D62828";del.style.color="#fff";del.innerHTML=ic("trash")+"Click again to delete";tm=setTimeout(()=>{armed=false;del.style.cssText="color:#FF9AA0";del.innerHTML=ic("trash")+"Delete"},3500);return}
    clearTimeout(tm);const id=N.cur.id;N.dirty=false;const r=await api("delete_note",id);if(!r.ok)return toast(r.error||"Couldn't delete.",{bad:1});
    toast("Deleted");N.cur=null;if(S.dockId===id){S.dockId=0;setP("dockId",0)}await loadNotes();drawNoteList();const f=N.list[0];f?openNote(f.id):showEmptyEd();drawDock(true)}}
  if(isS){
    $("#edDock").onclick=()=>{S.dockId=N.cur.id;setP("dockId",N.cur.id);toast("Pinned. Open it any time with the Script button or Ctrl+J.")};
    $("#edRead").onclick=()=>setRead(!N.read);
    $("#edMinus").onclick=()=>zoom(-10);$("#edPlus").onclick=()=>zoom(10);
  }
  savedState(n.unsynced?"Saving…":"Saved");
}
function zoom(d){const z=Math.max(60,Math.min(260,zoomOf()+d));setP("readZoom",z);const b=$("#edBody");b&&b.style&&(b.style.zoom=z/100);drawDock(true)}
function setRead(on){
  N.read=on;const b=$("#edBody"),tb=$("#edTb");if(!b||b.tagName==="TEXTAREA")return;
  b.contentEditable=on?"false":"true";b.classList.toggle("read",on);if(tb)tb.style.display=on?"none":"";
  $("#edRead").textContent=on?"Edit":"Reading mode";$("#edRead").classList.toggle("on",on);
  if(on)zoomIfSmall();
}
function zoomIfSmall(){if(zoomOf()<120){setP("readZoom",130);const b=$("#edBody");b&&(b.style.zoom=1.3);drawDock(true)}}
function toggleFocus(){const on=!document.body.classList.contains("focus");document.body.classList.toggle("focus",on);const f=$("#edFocus");if(f)f.textContent=on?"Leave focus":"Focus";if(on)toast("Focus mode. Press Esc to come back.",{ms:2200})}
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&document.body.classList.contains("focus")&&!$(".ov.on")){toggleFocus()}});
function touch(now){N.dirty=true;savedState("Saving…");clearTimeout(N.t);N.t=setTimeout(flushNote,now?60:700)}
async function flushNote(){
  clearTimeout(N.t);
  if(!N.cur||!N.dirty)return;
  if(N.saving){N.t=setTimeout(flushNote,300);return}
  const c=N.cur;N.dirty=false;N.saving=true;
  try{
    const r=await api("save_note",{id:c.id,kind:c.kind,scope:c.scope,title:c.title,folder:c.folder,body:c.body});
    if(!r.ok){N.dirty=true;savedState(r.error||"Couldn't save",true)}
    else{if(N.cur&&N.cur.id===c.id){N.serverBody=r.body!=null?r.body:c.body;N.serverTitle=c.title.trim()||"Untitled"}
      const i=N.list.findIndex(x=>x.id===c.id);if(i>=0)N.list[i]=Object.assign(N.list[i],{title:c.title.trim()||"Untitled",scope:c.scope,folder:c.folder.trim(),body:r.body!=null?r.body:c.body,unsynced:true});
      if(N.cur&&N.cur.id===c.id&&!N.dirty)savedState("Saved");drawNoteList();drawDock(true)}
  }catch(e){N.dirty=true;savedState("Couldn't save. Retrying…",true);N.t=setTimeout(flushNote,3000)}
  N.saving=false;
}
function refreshOpen(fresh){
  // Only act when ANOTHER computer changed this note (its text differs from what this app last loaded or saved),
  // and never while the person has unsaved typing. Our own saved copy coming back must not touch the editor.
  if(!N.cur||N.dirty||N.saving||fresh.id!==N.cur.id)return;
  const b=$("#edBody");if(!b)return;
  const bodyChanged=fresh.body!==N.serverBody,titleChanged=fresh.title!==N.serverTitle;
  if(!bodyChanged&&!titleChanged)return;
  const focused=document.activeElement===b||(b.contains&&b.contains(document.activeElement));
  if(focused)return;
  N.cur=Object.assign({},fresh);N.serverBody=fresh.body;N.serverTitle=fresh.title;
  if(fresh.kind==="script")b.innerHTML=sanHTML(fresh.body);else b.value=fresh.body;
  const t=$("#edTitle");if(t&&document.activeElement!==t)t.value=fresh.title;
}
window.addEventListener("beforeunload",()=>{if(N.dirty)flushNote()});
/* rich text */
const svgAl=(w)=>`<svg viewBox="0 0 16 16">${w.map((x,i)=>`<path d="M${x[0]} ${3+i*3.4}H${x[1]}"/>`).join("")}</svg>`;
function toolbarHTML(){
  const b=(c,l,t)=>`<button type="button" data-c="${c}" title="${t}" aria-label="${t}">${l}</button>`;
  return `<div class="tb" id="edTb" role="toolbar" aria-label="Formatting">
   ${b("undo","↶","Undo (Ctrl+Z)")}${b("redo","↷","Redo (Ctrl+Y)")}<i class="sep"></i>
   <select id="tbBlock" aria-label="Style"><option value="p">Normal text</option><option value="h1">Heading 1</option><option value="h2">Heading 2</option><option value="h3">Heading 3</option><option value="blockquote">Quote</option></select>
   <select id="tbFont" aria-label="Font">${FONTS.map(f=>`<option>${f}</option>`).join("")}</select>
   <select id="tbSize" aria-label="Text size"><option value="">Size</option>${SIZES.map(s=>`<option value="${s}">${s}</option>`).join("")}</select><i class="sep"></i>
   ${b("bold","<b>B</b>","Bold (Ctrl+B)")}${b("italic","<i>I</i>","Italic (Ctrl+I)")}${b("underline","<u>U</u>","Underline (Ctrl+U)")}${b("strikeThrough","<s>S</s>","Strikethrough")}<i class="sep"></i>
   <label class="tbc" title="Text color"><span class="a" id="tbColA">A</span><input type="color" id="tbColor" value="#17251d" aria-label="Text color"></label>
   <label class="tbc" title="Highlight color"><span class="a" id="tbHiA" style="background:#ffe27a;padding:0 3px;border-radius:3px;color:#17251D;border:0">ab</span><input type="color" id="tbHi" value="#ffe27a" aria-label="Highlight color"></label>${b("noHi","<span style='font-size:11px'>no hl</span>","Remove highlight")}<i class="sep"></i>
   ${b("insertUnorderedList","• List","Bullet list")}${b("insertOrderedList","1. List","Numbered list")}${b("outdent","⇤","Decrease indent")}${b("indent","⇥","Increase indent")}<i class="sep"></i>
   ${b("justifyLeft",svgAl([[2,14],[2,10],[2,14],[2,8]]),"Align left")}${b("justifyCenter",svgAl([[2,14],[4,12],[2,14],[5,11]]),"Align center")}${b("justifyRight",svgAl([[2,14],[6,14],[2,14],[8,14]]),"Align right")}${b("justifyFull",svgAl([[2,14],[2,14],[2,14],[2,14]]),"Justify")}<i class="sep"></i>
   ${b("link","Link","Add link (Ctrl+K)")}${b("unlink","Unlink","Remove link")}${b("removeFormat","Tx","Clear formatting")}</div>`;
}
function wireEditor(ed){
  const tb=$("#edTb");
  const saveSel=()=>{const s=getSelection();if(s.rangeCount&&ed.contains(s.anchorNode))N.sel=s.getRangeAt(0).cloneRange()};
  const restore=()=>{ed.focus();if(N.sel){const s=getSelection();s.removeAllRanges();s.addRange(N.sel)}};
  if(window.__selH)document.removeEventListener("selectionchange",window.__selH);
  window.__selH=()=>{saveSel();if(document.activeElement===ed)state()};      // remember the caret even if focus just moved to a toolbar list
  document.addEventListener("selectionchange",window.__selH);
  const state=()=>{if(!tb)return;["bold","italic","underline","strikeThrough","insertUnorderedList","insertOrderedList","justifyLeft","justifyCenter","justifyRight","justifyFull"].forEach(c=>{const b=$(`[data-c="${c}"]`,tb);if(b){let v=false;try{v=document.queryCommandState(c)}catch(e){}b.classList.toggle("on",v)}})};
  // With only a caret (nothing selected) browsers keep a fragile "typing style". An invisible styled span is reliable.
  const CARET={fontSize:["fontSize",x=>x+"px"],fontName:["fontFamily",x=>x],foreColor:["color",x=>x],hiliteColor:["backgroundColor",x=>x]};
  const caretStyle=(c,v)=>{const sel=getSelection();if(!sel.rangeCount||!sel.isCollapsed)return false;
    const [prop,fmt]=CARET[c],sp=document.createElement("span");sp.style[prop]=fmt(c==="fontSize"?lastPx:v);sp.textContent="\u200B";
    const r=sel.getRangeAt(0);r.insertNode(sp);const nr=document.createRange();nr.setStart(sp.firstChild,1);nr.collapse(true);sel.removeAllRanges();sel.addRange(nr);return true};
  const run=(c,v,css)=>{restore();
    if(CARET[c]&&c!=="fontSize"&&c!=="hiliteColor"||(c==="fontSize"||c==="hiliteColor")){const sel=getSelection();if(CARET[c]&&sel.rangeCount&&sel.isCollapsed&&ed.contains(sel.anchorNode)){if(c==="fontSize"){lastPx=pendingPx||lastPx;pendingPx=0}
      if(caretStyle(c,v)){saveSel();ed.dispatchEvent(new Event("input"));state();return}}}
    try{document.execCommand("styleWithCSS",false,!!css);document.execCommand(c,false,v==null?null:v)}catch(e){}saveSel();fix();ed.dispatchEvent(new Event("input"));state()};
  // execCommand fontSize only knows 1-7; swap those for exact pixel sizes
  let pendingPx=0;
  const fix=()=>{if(!pendingPx)return;lastPx=pendingPx;conv();pendingPx=0};
  let lastPx=0;
  const conv=()=>{ed.querySelectorAll('font[size="7"]').forEach(f=>{const s=document.createElement("span");s.style.fontSize=lastPx+"px";while(f.firstChild)s.appendChild(f.firstChild);f.replaceWith(s)});
    ed.querySelectorAll('[style*="xxx-large"]').forEach(s=>{s.style.fontSize=lastPx+"px"})};
  ed.addEventListener("input",()=>{if(lastPx)conv()});
  tb&&tb.addEventListener("mousedown",e=>{if(!e.target.closest("select,input"))e.preventDefault()});
  tb&&$$("[data-c]",tb).forEach(b=>b.onclick=()=>{
    const c=b.dataset.c;
    if(c==="link")return openLink();
    if(c==="noHi")return run("hiliteColor","transparent",true);
    run(c,null,false);
  });
  if(tb){
    $("#tbBlock",tb).onchange=e=>{run("formatBlock","<"+e.target.value+">",false)};
    $("#tbFont",tb).onchange=e=>{const v=e.target.value;if(v==="Default"){run("removeFormat");return}run("fontName",v,true)};
    $("#tbSize",tb).onchange=e=>{const v=+e.target.value;if(!v)return;pendingPx=v;run("fontSize","7",true);e.target.value=""};
    $("#tbColor",tb).oninput=e=>{$("#tbColA",tb).style.setProperty("--tbc",e.target.value);run("foreColor",e.target.value,true)};
    $("#tbHi",tb).oninput=e=>{$("#tbHiA",tb).style.background=e.target.value;run("hiliteColor",e.target.value,true)};
  }
  const bar=$("#lnkBar"),url=$("#lnkUrl");
  const openLink=()=>{saveSel();const a=getSelection().anchorNode;const el=a&&(a.nodeType===3?a.parentElement:a);const cur=el&&el.closest&&el.closest("a");url.value=cur?cur.getAttribute("href")||"":"https://";bar.classList.add("on");url.focus();url.select()};
  const apply=()=>{let v=url.value.trim();if(v&&!/^(https?:\/\/|mailto:|tel:)/i.test(v))v=/@/.test(v)?"mailto:"+v:"https://"+v;bar.classList.remove("on");if(!v||v==="https://"){return}
    restore();const s=getSelection();if(s.isCollapsed){run("insertHTML",`<a href="${esc(v)}" target="_blank" rel="noopener noreferrer">${esc(v)}</a>`,false)}else run("createLink",v,false)};
  $("#lnkOk").onclick=apply;$("#lnkNo").onclick=()=>{bar.classList.remove("on");restore()};url.onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();apply()}if(e.key==="Escape"){bar.classList.remove("on");restore()}};
  ed.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();openLink()}
    if(e.key==="Tab"){e.preventDefault();document.execCommand(e.shiftKey?"outdent":"indent")}});
  // paste keeps the formatting people copy from Google Docs or Word, but only safe formatting
  ed.addEventListener("paste",e=>{
    const cd=e.clipboardData;if(!cd)return;e.preventDefault();
    const h=cd.getData("text/html");
    if(h){document.execCommand("insertHTML",false,sanHTML(h.replace(/<!--[\s\S]*?-->/g,"")))}
    else{const t=cd.getData("text/plain");document.execCommand("insertHTML",false,esc(t).split(/\r?\n/).map(x=>x||"<br>").join("<br>"))}
    ed.dispatchEvent(new Event("input"));
  });
  ed.addEventListener("drop",e=>e.preventDefault());
  ed.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest("a");if(a&&(N.read||e.ctrlKey||e.metaKey)){e.preventDefault();window.open(a.href,"_blank")}else if(a)e.preventDefault()});
  ed.addEventListener("keyup",state);ed.addEventListener("mouseup",state);
  ed.addEventListener("blur",saveSel);
}
/* ---------------- docked script ---------------- */
function scriptsList(){return (S.nlist||[]).filter(n=>n.kind==="script")}
function applyDock(){
  const main=$("#main"),open=!!S.dockOpen&&S.page!=="notes"&&!!S.me;
  main.classList.toggle("hasdock",open);$("#scriptBtn").classList.toggle("on",!!S.dockOpen);
  main.style.setProperty("--dockw",(getP("dockW",380))+"px");
  if(open)drawDock(true);
  setTimeout(movePills,50);
}
async function toggleDock(force){
  S.dockOpen=force!=null?force:!S.dockOpen;setP("dockOpen",S.dockOpen);
  if(S.dockOpen&&!(S.nlist||[]).length)await loadNotes();
  applyDock();
}
function drawDock(q){
  const dk=$("#dock");if(!dk||!S.dockOpen)return;
  const list=scriptsList();
  if(!list.find(n=>n.id===S.dockId))S.dockId=(list[0]||{}).id||0;
  const n=list.find(x=>x.id===S.dockId);
  const sig=JSON.stringify([S.dockId,list.map(x=>[x.id,x.title,x.body.length,x.scope]),zoomOf(),S.dockFind||""]);
  if(q&&S.lastSig.dock===sig)return;S.lastSig.dock=sig;
  const sel=$("#dkSel");
  sel.innerHTML=list.length?list.map(x=>`<option value="${x.id}"${x.id===S.dockId?" selected":""}>${esc(x.title)}${x.scope==="shared"?" (team)":""}</option>`).join(""):`<option>No scripts yet</option>`;
  const body=$("#dkBody");
  if(!n){body.innerHTML=`<p style="color:#4b6355">You don't have a script yet.<br>Open <b>Notes</b>, press <b>+ Script</b>, write it once, and it stays here next to your phone numbers.</p>`;body.style.zoom=1;return}
  let html=sanHTML(n.body)||`<p style="color:#6b8576">This script is empty.</p>`;
  const f=(S.dockFind||"").trim();
  if(f&&f.length>1){const d=document.createElement("div");d.innerHTML=html;const w=document.createTreeWalker(d,NodeFilter.SHOW_TEXT),hits=[];while(w.nextNode())hits.push(w.currentNode);
    const re=new RegExp(f.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),"gi");
    hits.forEach(t=>{if(!re.test(t.nodeValue))return;re.lastIndex=0;const sp=document.createElement("span");sp.innerHTML=esc(t.nodeValue).replace(new RegExp(esc(f).replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),"gi"),m=>`<mark class="hit">${m}</mark>`);t.replaceWith(sp)});html=d.innerHTML}
  const keep=$("#dkPaper").scrollTop;body.innerHTML=html;body.style.zoom=zoomOf()/100;$("#dkPaper").scrollTop=keep;
}
(function(){
  const dk=$("#dock");
  $("#scriptBtn").onclick=()=>toggleDock();
  $("#dkX").onclick=()=>toggleDock(false);
  $("#dkSel").onchange=e=>{S.dockId=+e.target.value;setP("dockId",S.dockId);drawDock()};
  $("#dkMinus").onclick=()=>zoom(-10);$("#dkPlus").onclick=()=>zoom(10);
  $("#dkEdit").onclick=async()=>{await go("notes");const id=S.dockId;if(id)openNote(id)};
  $("#dkFind").oninput=e=>{S.dockFind=e.target.value;drawDock()};
  $("#dkBody").addEventListener("click",e=>{const a=e.target.closest("a");if(a){e.preventDefault();window.open(a.href,"_blank")}});
  document.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="j"){e.preventDefault();if(S.me)toggleDock()}});
  const grip=$("#dkGrip");
  grip.addEventListener("mousedown",e=>{e.preventDefault();const main=$("#main"),r=main.getBoundingClientRect();
    const mv=ev=>{const w=Math.max(280,Math.min(r.width*0.7,r.right-ev.clientX));main.style.setProperty("--dockw",w+"px");setP("dockW",Math.round(w))};
    const up=()=>{document.removeEventListener("mousemove",mv);document.removeEventListener("mouseup",up);setTimeout(movePills,60)};
    document.addEventListener("mousemove",mv);document.addEventListener("mouseup",up)});
})();

/* ---------------- shared call log ---------------- */
const OUT={no_answer:["No answer","#EB955A","#F4BC8F"],voicemail:["Voicemail","#9FB2A6","#C9D6CE"],interested:["Interested","#E9C15A","#F1D58C"],not_interested:["Not interested","#E46F6F","#F3A3A3"],follow_up:["Follow-up","#7FAEF0","#B4CFF6"],meeting_booked:["Meeting booked","#3FD487","#8DF0BB"],sale_completed:["Sale completed","#B7E05A","#D6EF9C"]};
const opill=o=>{const x=OUT[o]||[o,"#9FB2A6","#C9D6CE"];return `<span class="op" style="background:color-mix(in srgb,${x[1]} 15%,transparent);color:${x[2]};box-shadow:inset 0 0 0 1px color-mix(in srgb,${x[1]} 38%,transparent)">${esc(x[0])}</span>`};
const CF={employee:"",outcome:"",from:"",to:"",q:"",range:"7"};
function setRange(r){CF.range=r;const t=new Date();CF.to="";if(r==="today")CF.from=isoDay(t);else if(r==="all")CF.from="";else{const d=new Date(t);d.setDate(d.getDate()-(+r-1));CF.from=isoDay(d)}}
setRange("7");
let clTok=0,clTimer=0;
const clTime=iso=>{const d=new Date(iso);return isNaN(d)?"":d.toLocaleDateString("en-US",{month:"short",day:"numeric"})+" · "+d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})};
async function renderCalls(soft){
  const pg=$("#pg-calls");
  if(!pg.dataset.built){
    pg.dataset.built=1;
    pg.innerHTML=`<div class="cl"><div class="card cl-f pop">
      <div><label class="l" for="clWho">Employee</label><select id="clWho" style="min-width:150px"></select></div>
      <div><label class="l" for="clOut">Outcome</label><select id="clOut" style="min-width:150px"><option value="">Every outcome</option>${Object.keys(OUT).map(k=>`<option value="${k}">${OUT[k][0]}</option>`).join("")}</select></div>
      <div><label class="l" for="clFrom">From</label><input class="inp" type="date" id="clFrom"></div>
      <div><label class="l" for="clTo">To</label><input class="inp" type="date" id="clTo"></div>
      <div style="flex:1;min-width:170px"><label class="l" for="clQ">Business, phone or note</label><input class="inp" id="clQ" placeholder="Search prospects" autocomplete="off"></div>
      <div style="display:flex;gap:6px;flex-direction:row" id="clRange"><button class="chip" data-r="today">Today</button><button class="chip" data-r="7">7 days</button><button class="chip" data-r="30">30 days</button><button class="chip" data-r="all">All time</button></div>
      <button class="btn pri" id="clLog">${ic("plus")}Log a call</button></div>
      <div class="cl-sum" id="clSum"></div>
      <div class="card pop" style="padding:6px 8px;overflow:auto"><div id="clBody"><div class="cl-sk" aria-label="Loading calls"><i></i><i></i><i></i><i></i><i></i></div></div></div></div>`;
    hydrateIcons(pg);
    const upd=()=>{CF.employee=$("#clWho").value;CF.outcome=$("#clOut").value;CF.from=$("#clFrom").value;CF.to=$("#clTo").value;CF.range="";paintRange();renderCalls(true)};
    ["clWho","clOut","clFrom","clTo"].forEach(i=>$("#"+i).onchange=upd);
    $("#clQ").oninput=e=>{CF.q=e.target.value;clearTimeout(clTimer);clTimer=setTimeout(()=>renderCalls(true),350)};
    $$("#clRange [data-r]").forEach(b=>b.onclick=()=>{setRange(b.dataset.r);$("#clFrom").value=CF.from;$("#clTo").value="";paintRange();renderCalls(true)});
    $("#clLog").onclick=()=>logCallModal();
  }
  const who=$("#clWho");
  const opts=`<option value="">Everyone</option>`+(S.people||[]).filter(p=>p.active!==false).map(p=>`<option value="${esc(p.id)}">${esc(p.display_name)}</option>`).join("")+`<option value="none">Unassigned (older data)</option>`;
  if(who.dataset.sig!==opts){who.innerHTML=opts;who.dataset.sig=opts}
  who.value=CF.employee;$("#clOut").value=CF.outcome;$("#clFrom").value=CF.from;$("#clTo").value=CF.to;
  paintRange();
  const my=++clTok;let r;$("#clBody").classList.add("busy");
  try{r=await api("get_calls",Object.fromEntries(Object.entries(CF).filter(([k,v])=>v&&k!=="range")))}catch(e){r={ok:false,error:"The app engine did not respond."}}
  if(my!==clTok||S.page!=="calls")return;
  const body=$("#clBody"),sum=$("#clSum");body.classList.remove("busy");
  if(!r.ok){body.innerHTML=`<div class="empty" style="padding:40px 10px"><b>The call log isn't available</b>${esc(r.error||"")}</div>`;sum.innerHTML="";return}
  const rows=r.rows,cnt={};rows.forEach(x=>cnt[x.outcome]=(cnt[x.outcome]||0)+1);
  /* a new filter (or opening the page) replays the whole cascade; the 20-second refresh only animates calls that just came in */
  const fsig=JSON.stringify([CF.employee,CF.outcome,CF.from,CF.to,CF.q]),full=!soft||body.dataset.f!==fsig,rk=x=>[x.at,x.who,x.phone,x.outcome,x.business].join("|");
  const seen=new Set((body.dataset.k||"").split("\n"));body.dataset.f=fsig;body.dataset.k=rows.slice(0,300).map(rk).join("\n");
  const chipC=full?" cin":"",prevN=JSON.parse(sum.dataset.n||"{}"),nowN={_:rows.length,...cnt};sum.dataset.n=JSON.stringify(nowN);
  let ci=0;const cn=(k,v)=>`<b data-cn="${v}" data-from="${full?0:(prevN[k]||0)}">${full?0:v}</b>`;
  sum.innerHTML=`<button class="${CF.outcome?"":"on"}${chipC}" style="--i:${ci++}" data-o="">${cn("_",rows.length)} ${rows.length===1?"call":"calls"}</button>`+Object.keys(OUT).filter(k=>cnt[k]).map(k=>`<button class="${CF.outcome===k?"on":""}${chipC}" style="--i:${ci++}" data-o="${k}">${opill(k)}${cn(k,cnt[k])}</button>`).join("")+(r.stale?`<span class="muted" style="align-self:center;font-size:12.5px">Offline: showing the last list loaded.</span>`:"")+(r.capped?`<span class="muted" style="align-self:center;font-size:12.5px">Showing the newest 1000. Narrow the dates to see others.</span>`:"");
  $$("[data-o]",sum).forEach(b=>b.onclick=()=>{CF.outcome=b.dataset.o;$("#clOut").value=CF.outcome;renderCalls(true)});
  $$("[data-cn]",sum).forEach(e=>{const to=+e.dataset.cn,fr=+e.dataset.from;if(fr===to){e.textContent=num(to);return}
    if(REDUCE){e.textContent=num(to);return}const t0=performance.now(),ms=full?700:500;(function f(t){const k=Math.min(1,(t-t0)/ms),v=fr+(to-fr)*(1-Math.pow(1-k,3));e.textContent=num(Math.round(v));if(k<1)requestAnimationFrame(f)})(t0)});
  const rowCls=(x,i)=>full?(i<40?` class="rin" style="--i:${i}"`:""):seen.has(rk(x))?"":` class="rin fresh"`;
  body.innerHTML=rows.length?`<table class="tbl"><tr><th>When</th><th>Who</th><th>Business</th><th>Phone</th><th>Outcome</th><th>Notes</th></tr>${rows.map((x,i)=>`<tr${rowCls(x,i)}><td>${esc(clTime(x.at))}</td><td>${esc(x.who)}</td><td><b>${esc(x.business||"—")}</b>${x.legacy?`<br><span class="tag">From older records</span>`:""}${x.pending?`<br><span class="tag scr">Waiting to sync</span>`:""}</td><td>${esc(x.phone||"")}</td><td>${opill(x.outcome)}</td><td class="nt2">${esc(x.notes||"")}</td></tr>`).join("")}</table>`
    :`<div class="empty" style="padding:50px 10px"><b>No calls match</b>Change the filters, or press Log a call to add one.</div>`;
}
function paintRange(){$$("#clRange [data-r]").forEach(b=>b.classList.toggle("on",b.dataset.r===CF.range))}
function logCallModal(lead){
  const pool=[...S.called,...S.find],seen=new Set(),names=pool.filter(l=>l.name&&!seen.has(l.name)&&seen.add(l.name));
  const now=new Date(),loc=new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,16);
  let out="";
  openModal(`<h2>Log a call</h2>
   <div class="fg"><div style="grid-column:1/3"><label class="l" for="lcBiz">Business (pick from your list or type a phone number below)</label><input class="inp" id="lcBiz" list="lcList" placeholder="Start typing a business name" value="${esc(lead?lead.name:"")}" style="width:100%"><datalist id="lcList">${names.slice(0,2000).map(l=>`<option value="${esc(l.name)}">`).join("")}</datalist></div>
   <div><label class="l" for="lcPhone">Phone</label><input class="inp" id="lcPhone" value="${esc(lead?lead.phone:"")}" placeholder="(555) 555-5555"></div>
   <div><label class="l" for="lcWhen">When</label><input class="inp" id="lcWhen" type="datetime-local" value="${loc}"></div></div>
   <label class="l">What happened?</label><div class="oc" id="lcOut">${Object.keys(OUT).map(k=>`<button type="button" data-o="${k}"><i style="background:${OUT[k][1]}"></i>${OUT[k][0]}</button>`).join("")}</div>
   <label class="l" for="lcNotes">Notes (optional)</label><input class="inp" id="lcNotes" maxlength="500" style="width:100%" placeholder="Anything worth remembering">
   <div style="display:flex;gap:10px;margin-top:20px;justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn pri" data-save>Save call</button></div>`,
  (ov,close)=>{
    const g=i=>$("#"+i,ov);
    g("lcBiz").onchange=()=>{const l=pool.find(x=>x.name===g("lcBiz").value);if(l)g("lcPhone").value=l.phone};
    $$("#lcOut button",ov).forEach(b=>b.onclick=()=>{out=b.dataset.o;$$("#lcOut button",ov).forEach(x=>x.classList.toggle("on",x===b))});
    $("[data-x]",ov).onclick=close;
    $("[data-save]",ov).onclick=async()=>{
      const l=pool.find(x=>x.name===g("lcBiz").value);
      const r=await api("log_call",{lead_id:l?l.id:(lead?lead.id:""),phone:g("lcPhone").value,when:g("lcWhen").value,outcome:out,notes:g("lcNotes").value});
      if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1});
      close();toast("Call logged");if(S.page==="calls")renderCalls(true)};
  });
}
setInterval(()=>{if(S.ready&&S.page==="calls"&&!document.hidden&&!$(".ov.on"))renderCalls(true)},20000);

/* ---------------- admin ---------------- */
async function renderAdmin(){
  const pg=$("#pg-admin");
  if(!S.me||S.me.role!=="admin"){pg.innerHTML=`<div class="card empty" style="margin-top:40px"><b>Administrators only</b>This page is for James, Omar and Akbar.</div>`;return}
  if(!pg.querySelector(".ad"))pg.innerHTML=`<div class="empty" style="margin-top:80px"><div class="spin"></div><b>Loading the admin tools...</b></div>`;
  const tmo=(pr,ms)=>Promise.race([pr,new Promise(r=>setTimeout(()=>r({ok:false,error:"The shared database took too long to answer."}),ms))]);
  const [a1,a2]=await Promise.allSettled([tmo(api("admin_people"),15000),tmo(api("get_team"),15000)]);
  let r=a1.status==="fulfilled"&&a1.value?a1.value:{ok:false,error:"The app engine did not respond."},t=a2.status==="fulfilled"?a2.value:null;
  if(S.page!=="admin")return;
  if(!r.ok){pg.innerHTML=`<div class="card empty" style="margin-top:40px"><div class="bub">${ic("shield")}</div><b>Can't load the admin tools</b>${esc(r.error||"")}<button class="btn" id="adRetry" style="margin-top:8px">Try again</button></div>`;$("#adRetry").onclick=()=>renderAdmin();return}
  const T=r.targets&&r.targets.calls!==undefined?r.targets:(t&&t.targets)||{calls:100,connections:20,meetings:3,sales:1};
  const per={};(t&&t.people||[]).forEach(p=>per[p.id]=p);
  const ago=iso=>{if(!iso)return "never";const m=Math.round((Date.now()-new Date(iso))/60000);return m<2?"just now":m<60?m+" min ago":m<1440?Math.round(m/60)+" h ago":Math.round(m/1440)+" d ago"};
  pg.innerHTML=`<div class="ad">
   <div class="card"><h3>Daily targets</h3><div class="muted" style="font-size:13px">These are what the progress bars on the Team page measure against, for every employee.</div>
    <div class="ad-t">${[["calls","Calls"],["connections","Connections"],["meetings","Meetings"],["sales","Sales"]].map(([k,l])=>`<div><label class="l" for="tg_${k}">${l} per day</label><input class="inp" type="number" min="0" max="9999" id="tg_${k}" value="${+T[k]||0}"></div>`).join("")}</div>
    <button class="btn pri" id="tgSave">Save targets</button></div>
   <div class="card"><h3>People</h3>
    <table class="tbl"><tr><th>Name</th><th>Login</th><th>Role</th><th>Last seen</th><th>Active</th></tr>
    ${r.people.map(p=>{const me=S.me.id===p.id;return `<tr><td><b>${esc(p.display_name)}</b>${me?" (you)":""}${p.must_change_password?`<br><span class="tag scr">Has not changed the starter password</span>`:""}</td><td>${esc(p.username)}</td>
     <td><select data-role="${esc(p.id)}"${me?" disabled":""}><option value="employee"${p.role==="employee"?" selected":""}>Employee</option><option value="admin"${p.role==="admin"?" selected":""}>Administrator</option></select></td>
     <td>${esc(ago(p.last_seen))}</td><td><button class="tg${p.active?" on":""}" data-act="${esc(p.id)}"${me?" disabled":""} aria-label="${p.active?"Deactivate":"Activate"} ${esc(p.display_name)}" aria-pressed="${p.active}"></button></td></tr>`}).join("")}</table>
    <div class="muted" style="font-size:13px;line-height:1.55;margin-top:12px">A deactivated person is signed out within about a minute and cannot sign back in. Their calls, leads and notes stay in the shared database.<br>
    <b>To add an employee or reset a password:</b> double-click <b>ADMIN_TOOLS.bat</b> in the Leafline folder on your computer. It needs the private server key, which is deliberately never inside this app.</div></div>
   <div class="card"><h3>Everyone's numbers · last ${(t&&t.series?t.series.length:14)} days</h3>
    <table class="tbl"><tr><th>Name</th><th>Calls</th><th>Connected</th><th>Prospects</th><th>Meetings</th><th>Sales</th></tr>
    ${(t&&t.people||[]).map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${p.period.calls}</td><td>${p.period.connections}</td><td>${p.period.prospects}</td><td>${p.period.meetings}</td><td>${p.period.sales}</td></tr>`).join("")||`<tr><td colspan="6" class="muted">No numbers yet.</td></tr>`}</table></div>
   <div class="card"><h3>Export company data</h3><div class="muted" style="font-size:13px;line-height:1.55;margin-bottom:12px">Saves the shared database as spreadsheet files (leads, calls, deals, calendar events, people). Pick a file name; five files are written next to it.</div>
    <button class="btn" id="adExport">${ic("down")}Export everything</button></div></div>`;
  hydrateIcons(pg);
  $("#tgSave").onclick=async()=>{const body={};["calls","connections","meetings","sales"].forEach(k=>body[k]=+$("#tg_"+k).value||0);
    const x=await api("admin_targets",body);x.ok?toast("Targets saved for everyone"):toast(x.error||"Couldn't save.",{bad:1})};
  $$("[data-role]",pg).forEach(s=>s.onchange=async()=>{const x=await api("admin_update",s.dataset.role,s.value,null);x.ok?toast("Role updated"):(toast(x.error||"Couldn't update.",{bad:1}),renderAdmin())});
  $$("[data-act]",pg).forEach(b=>b.onclick=async()=>{const on=!b.classList.contains("on");
    if(!on&&!confirm("Deactivate this person? They will be signed out and unable to sign in."))return;
    const x=await api("admin_update",b.dataset.act,null,on);x.ok?(toast(on?"Reactivated":"Deactivated"),renderAdmin()):toast(x.error||"Couldn't update.",{bad:1})});
  $("#adExport").onclick=async()=>{
    let path="";try{if(window.leafline&&window.leafline.saveCsv){path=await window.leafline.saveCsv("leafline_company_"+isoDay(new Date())+".csv");if(!path)return}}catch(e){}
    toast("Exporting…",{ms:1500});const x=await api("admin_export",path);
    x.ok?alertBox("Export finished",x.files.map(f=>f.file+" — "+f.rows+" rows").join("\n")+"\n\nSaved in: "+x.folder):toast(x.error||"Export failed.",{bad:1})};
}

/* ---------------- ACCOUNT ---------------- */
const SW=["#3DDC84","#5EE6B8","#FFD60A","#FF9F43","#F2788A","#7FB6FF"];
function renderAccount(){
  const p=S.profile,st=S.stats||{called:0,meetings:0,total:0},pg=$("#pg-account");
  const hasAv=!!(S.me&&(S.me.avatar||(S.me.media&&S.me.media.avatar_url)));
  pg.innerHTML=`<div class="acc"><div class="card idc pop">${S.me?bannerHTML({ext:S.me.ext,media:S.me.media}):""}<div class="ring"><div class="in-av" data-live id="accAv">LF</div><span class="dot"></span></div>
   ${S.me?bdgSlot(S.me.id,8,true).replace('class="bdg"','class="bdg bdg-list"'):""}
   <div class="avbtns"><button class="btn sm" id="avUp">${ic("plus")}Upload photo</button><button class="btn sm" id="avDel"${hasAv?"":" style='display:none'"}>Remove</button><input type="file" id="avFile" accept="image/gif,image/webp,image/png,image/jpeg,image/avif" hidden></div>
   <div class="muted" style="font-size:12px;margin-top:6px">GIF, WebP, PNG, JPEG or AVIF up to 8 MB. Animations are kept.</div>
   <h2 id="accName">${esc(p.name||"Your name")}</h2><div class="sub" id="accRole">${esc([p.role,p.company].filter(Boolean).join(" · ")||"Leafline Web Services")}</div>
   <div class="sw" role="radiogroup" aria-label="Avatar color">${SW.map(c=>`<button style="background:${c}" data-c="${c}" class="${p.color===c?"on":""}" role="radio" aria-checked="${p.color===c}" aria-label="Color ${c}"></button>`).join("")}</div>
   <div class="mini"><div><b>${num(st.total)}</b><span>Leads</span></div><div><b>${num(st.called)}</b><span>Called</span></div><div><b>${num(st.meetings)}</b><span>Meetings</span></div></div></div>
  <div class="accr"><div class="card form pop"><h3>Account details</h3><div class="note">These are for show only right now. They are saved on this computer and are never sent anywhere.</div>
   <div class="fg">
    <div><label class="l" for="aName">Full name</label><input class="inp" id="aName" maxlength="80" value="${esc(p.name)}" placeholder="Your name"></div>
    <div><label class="l" for="aRole">Role</label><input class="inp" id="aRole" maxlength="80" value="${esc(p.role)}" placeholder="e.g. Sales rep"></div>
    <div><label class="l" for="aEmail">Email</label><input class="inp" id="aEmail" type="email" maxlength="80" value="${esc(p.email)}" placeholder="you@example.com"></div>
    <div><label class="l" for="aPhone">Phone</label><input class="inp" id="aPhone" maxlength="40" value="${esc(p.phone)}" placeholder="(555) 555-5555"></div>
    <div><label class="l" for="aCo">Company</label><input class="inp" id="aCo" maxlength="80" value="${esc(p.company)}"></div>
    <div><label class="l" for="aGoal">Daily call goal</label><input class="inp" id="aGoal" type="number" min="1" max="500" value="${p.goal}"></div>
    <div><label class="l" for="aCountry">Default country for searches</label><input class="inp" id="aCountry" maxlength="80" value="${esc(p.country)}"></div>
    <div><label class="l" for="aMax">Max businesses per search (10 to 120)</label><input class="inp" id="aMax" type="number" min="10" max="120" value="${p.max_results}"></div></div>
   <div style="display:flex;align-items:center;gap:14px"><button class="btn pri" id="aSave">Save changes</button><span class="note" id="dbNote"></span></div></div>
  ${(()=>{const ex=(S.me&&S.me.ext)||{};return `<div class="card form pop" id="extCard"><h3>Your public profile</h3><div class="note">Everyone on the team can see this on the Team page.</div>
   <div class="pbanw" style="margin-top:14px"><div class="pban has-img" id="bnPrev"></div><div class="avbtns"><button class="btn sm" id="bnUp">Upload banner</button><button class="btn sm" id="bnDel">Remove banner</button><input type="file" id="bnFile" accept="image/gif,image/webp,image/png,image/jpeg,image/avif" hidden></div></div>
   <div class="fg">
    <div><label class="l" for="xTitle">Job title</label><input class="inp" id="xTitle" maxlength="40" value="${esc(ex.title||"")}" placeholder="e.g. Sales rep"></div>
    <div><label class="l">Mood</label><div class="moods" id="xMoods">${MOODS.map(m=>`<button type="button" data-m="${m}" class="${ex.mood===m?"on":""}" aria-label="Mood ${m}">${m}</button>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l" for="xBio">Bio</label><textarea class="inp" id="xBio" maxlength="280" rows="3" placeholder="A line or two about you">${esc(ex.bio||"")}</textarea><div class="note"><span id="xBioN">0</span>/280</div></div>
    <div style="grid-column:1/3"><label class="l" for="xTh">Thought of the day</label><input class="inp" id="xTh" maxlength="140" value="${esc(freshThought(ex)?ex.thought:"")}" placeholder="Something to share with the team today"></div>
    <div style="grid-column:1/3"><label class="l">Profile colour</label><div class="sw" id="xAcc" style="justify-content:flex-start;margin:6px 0 0">${ACCENTS.map(c=>`<button type="button" style="background:${c}" data-a="${c}" class="${(okAccent(ex.accent)||ACCENTS[0])===c?"on":""}" aria-label="Colour ${c}"></button>`).join("")}</div></div></div>
   <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap"><button class="btn pri" id="xSave">Save profile</button><span class="note" id="xNote"></span></div></div>
  <div class="card form pop" id="themeCard"><h3>Appearance</h3><div class="note">Three dark green themes. Your choice follows you to every device you sign in on.</div>
   <div class="lgt-lbl" style="margin-top:14px"><div class="lgt big" data-lgt aria-label="Theme" role="radiogroup"></div><span>Forest · Emerald · Midnight</span></div></div>
  ${leadgenCard()}
  <div class="card form pop" id="updCard"><h3>App &amp; updates</h3>
   <div class="upd"><div><b id="updVer">Version</b><div class="note" id="updNote"></div><div class="bar" id="updBar"><i></i></div></div><button class="btn" id="updBtn">Check for updates</button></div></div></div></div>`})()}`;
  hydrateIcons(pg);profileUI();
  const live=()=>{const n=$("#aName").value.trim(),r=$("#aRole").value.trim(),c=$("#aCo").value.trim();
    $("#accName").textContent=n||"Your name";$("#accRole").textContent=[r,c].filter(Boolean).join(" · ")||"Leafline Web Services";
    if(!(S.me&&S.me.avatar)){$$("[data-live]").forEach(e=>e.textContent=n?initials(n):"LF");$("#sideAv").textContent=n?initials(n):"LF"}};
  $("#avUp").onclick=()=>$("#avFile").click();
  $("#avFile").onchange=e=>{const f=e.target.files[0];e.target.value="";mediaDialog("avatar",f)};
  $("#avDel").onclick=()=>clearMedia("avatar");
  paintLgt();wireLeadgen(pg);
  ["aName","aRole","aCo"].forEach(i=>$("#"+i).oninput=live);
  $$(".sw button",pg).forEach(b=>b.onclick=()=>{$$(".sw button",pg).forEach(x=>{x.classList.toggle("on",x===b);x.setAttribute("aria-checked",x===b)});S.profile.color=b.dataset.c;profileUI();bump(b)});
  $("#aSave").onclick=async()=>{
    const d={name:$("#aName").value,role:$("#aRole").value,email:$("#aEmail").value,phone:$("#aPhone").value,company:$("#aCo").value,country:$("#aCountry").value,
      goal:$("#aGoal").value,max_results:$("#aMax").value,color:S.profile.color};
    try{S.profile=await api("save_profile",d);profileUI();applyCountry(true);toast("Account saved");bump($("#aSave"));S.lastSig={};await reload()}catch(e){toast("Couldn't save: "+e.message,{bad:1})}
  };
  $("#dbNote").textContent=S.dbPath&&!window.LF_API?"Data folder: "+S.dbPath:"";
  /* public profile */
  {const ex0=(S.me&&S.me.ext)||{};let bn,mood=ex0.mood||"",acc=okAccent(ex0.accent)||ACCENTS[0];
   {const b0=bannerOf({ext:ex0,media:S.me&&S.me.media});$("#bnPrev").style.setProperty("--bp",b0.pos+"%");$("#bnPrev").innerHTML=imgTag(b0.src,b0.still);$("#bnDel").style.display=b0.src?"":"none"}
   $("#bnUp").onclick=()=>$("#bnFile").click();
   $("#bnFile").onchange=e=>{const f=e.target.files[0];e.target.value="";mediaDialog("banner",f)};
   $("#bnDel").onclick=()=>clearMedia("banner");
   $$("#xMoods button").forEach(b=>b.onclick=()=>{mood=(mood===b.dataset.m)?"":b.dataset.m;$$("#xMoods button").forEach(x=>x.classList.toggle("on",x.dataset.m===mood))});
   $$("#xAcc button").forEach(b=>b.onclick=()=>{acc=b.dataset.a;$$("#xAcc button").forEach(x=>x.classList.toggle("on",x===b));bump(b)});
   const cnt=()=>{$("#xBioN").textContent=$("#xBio").value.length};cnt();$("#xBio").oninput=cnt;
   $("#xSave").onclick=async()=>{
     const d={title:$("#xTitle").value,mood,bio:$("#xBio").value,thought:$("#xTh").value,accent:acc};
     const r=await api("set_profile_ext",d);if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1});
     S.me.ext=r.ext;bn=undefined;bump($("#xSave"));toast("Profile saved");
     $("#xNote").textContent=r.shared?"The team can see your changes.":"Saved on this device. It will be shared once the database update (step 4 in the setup guide) is applied."};}
  initUpdates().then(()=>{paintUpd();$("#updBtn").onclick=checkUpdatesNow;if(!UP){$("#updCard").style.display="none"}});
}
function applyCountry(force){const c=$("#fCountry");if(force||!c.value)c.value=S.profile.country||""}

/* ---------------- app updates (desktop installer or website; same card) ---------------- */
const UP=(window.leafline&&window.leafline.checkUpdate)?window.leafline:(window.LF_WEB||null);
const UPS={state:"idle",version:"",latest:"",percent:0,error:"",platform:""};
function paintUpd(){
  const n=$("#updNote"),b=$("#updBtn"),v=$("#updVer"),bar=$("#updBar");if(!n)return;
  const web=UPS.platform==="web",s=UPS.state;
  v.textContent="Version "+(UPS.version||"?")+(web?" (website)":" (desktop)");
  let t="New versions are installed automatically each time you open the app.",lab="Check for updates";
  if(s==="checking")t="Checking for updates...";
  else if(s==="none")t="You're on the latest version.";
  else if(s==="available"||s==="downloading")t=`Downloading version ${UPS.latest||""}${UPS.percent?" ("+Math.round(UPS.percent)+"%)":"..."}`;
  else if(s==="ready"){t=web?`Version ${UPS.latest} is ready.`:`Version ${UPS.latest} is downloaded. It installs when you restart.`;lab=web?"Reload now":"Restart & update"}
  else if(s==="building")t="A new version is still being built online. It downloads by itself in a few minutes; nothing to do.";
    else if(s==="error"){t=UPS.error||"Couldn't check for updates.";lab="Try again"}
  n.textContent=t;b.textContent=lab;b.disabled=(s==="checking"||s==="available"||s==="downloading");
  bar.style.display=(s==="downloading"||s==="available")?"block":"none";$("i",bar).style.width=(UPS.percent||0)+"%";
}
async function initUpdates(){
  if(!UP||initUpdates.done)return;initUpdates.done=true;
  try{const i=await UP.appInfo();UPS.version=i.version;UPS.platform=i.platform||"desktop"}catch(e){}
  UP.onUpdate(st=>{Object.assign(UPS,st);paintUpd();
    if(st.state==="ready"&&S.updToast!==st.latest){S.updToast=st.latest;toast(`Update ${st.latest||""} is ready`,{ms:20000,action:{label:UPS.platform==="web"?"Reload":"Restart",fn:()=>UP.installUpdate()}});logNote("An app update is ready ("+(st.latest||"")+")")}});
  try{const c=await (UP.status?UP.status():null);c&&Object.assign(UPS,c)}catch(e){}
}
async function checkUpdatesNow(){
  if(!UP)return;
  if(UPS.state==="ready")return UP.installUpdate();
  UPS.state="checking";paintUpd();
  try{const r=await UP.checkUpdate();if(r)Object.assign(UPS,r)}catch(e){UPS.state="error";UPS.error="Couldn't check: "+e.message}
  paintUpd();
}
/* ---------------- profile extras: title, bio, mood, thought of the day, banner ---------------- */
const ACCENTS=["#3DDC84","#4DD0E1","#5C9DFF","#B388FF","#FF7EB6","#FF5C5C","#FF9F43","#FFD60A"];
const MOODS=["😀","😎","🔥","💪","🚀","☕","🎯","🤝","🎧","😴"];
const okAccent=a=>/^#[0-9A-Fa-f]{6}$/.test(a||"")?a:"";
const safeBanner=u=>(typeof u==="string"&&u.length<160000&&IMG_OK.test(u))?u:"";
const freshThought=x=>!!(x&&x.thought&&x.thought_at&&Date.now()-new Date(x.thought_at).getTime()<36*3600e3);
function bannerFromFile(file){
  return new Promise((res,rej)=>{
    if(!file||!/^image\//.test(file.type))return rej(new Error("Pick an image file (JPG, PNG or WebP)."));
    if(file.size>20e6)return rej(new Error("That image is too big. Pick one under 20 MB."));
    const url=URL.createObjectURL(file),im=new Image();
    im.onload=()=>{try{URL.revokeObjectURL(url);res(fitStill(im,1,145000))}catch(e){rej(e)}};
    im.onerror=()=>{URL.revokeObjectURL(url);rej(new Error("Couldn't read that picture. Try a JPG or PNG."))};im.src=url});
}
function personModal(p){
  if(!p)return;const ext=p.ext||{},mine=!!(S.me&&S.me.id===p.id),acc=okAccent(ext.accent)||"#4ADE8B";
  if(mine)p={...p,avatar:S.me.avatar,media:S.me.media,ext:{...ext,banner:(S.me.ext||{}).banner}};
  const bn=bannerOf(p);
  openModal(`<div class="pcard" style="--acc:${acc}"><div class="pban has-img" id="pBan" style="--bp:${bn.pos}%">${imgTag(bn.src,bn.still)}</div><div class="pav">${avHTML(p.name,p.avatar,p.media)}</div>
   <h2>${esc(p.name)}${ext.mood?` <span class="pm">${esc(ext.mood)}</span>`:""}${streakChip(p.id,{zero:true,big:true})}</h2>
   <div class="sub">${esc([ext.title,p.role==="admin"?"Admin":"Rep"].filter(Boolean).join(" · "))} · <span class="${p.online?"on":""}">${p.online?"Online":"Offline"}</span></div>
   ${bdgSlot(p.id,8,true).replace('class="bdg"','class="bdg bdg-list"')}
   ${ext.bio?`<p class="pbio2">${esc(ext.bio)}</p>`:""}
   ${freshThought(ext)?`<div class="pth">“${esc(ext.thought)}”<small>Thought of the day</small></div>`:""}
   ${p.today?`<div class="mini"><div><b>${p.today.calls}</b><span>Calls today</span></div><div><b>${p.today.meetings}</b><span>Meetings</span></div><div><b>${p.today.sales}</b><span>Sales</span></div></div>`:""}
   <div style="text-align:right;margin-top:18px"><button class="btn pri" data-x>Close</button></div></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    ensureBoard();
    if(!mine&&!bn.src)api("get_person",p.id).then(r=>{if(!r||!r.ok||!r.person)return;const q=r.person,b2=bannerOf({ext:{banner:q.banner},media:{banner_url:q.banner_url,banner_pos:q.banner_pos}});
      if(b2.src){const el=$("#pBan",ov);el.style.setProperty("--bp",b2.pos+"%");el.innerHTML=imgTag(b2.src,b2.still)}}).catch(()=>{})});
}
/* ---------------- search ---------------- */
function setRunning(b){
  S.running=b;const g=$("#goBtn");g.classList.toggle("stop",b);g.classList.remove("pri");g.classList.toggle("pri",!b);
  $("span",g).textContent=b?"Stop":"Search";$("#pbar").classList.toggle("run",b);
}
function sText(t){const e=$("#sText");if(e.textContent!==t)e.textContent=t}
function progress(d){if(d.text)sText(d.text);if(d.frac!=null)$("#pfill").style.width=Math.round(d.frac*100)+"%"}
async function startSearch(){
  if(S.running){try{await api("stop")}catch(e){}$("#goBtn span").textContent="Stopping...";return}
  const v=id=>$("#"+id).value.trim(),type=v("fType"),area=[v("fCity"),v("fState"),v("fCountry")].filter(Boolean).join(", ");
  if(!type||!area)return toast("Enter a business type and at least a country, state/province or city.",{bad:1});
  try{const r=await api("search",v("fCountry"),v("fState"),v("fCity"),type);if(!r.ok)return toast(r.error||"Couldn't start the search.",{bad:1});
    S.current=r.q;S.scope="current";$("#scope").value="current";S.find=[];S.active=null;S.sel.clear();lastDetail=null;$("#pfill").style.width="0%";setRunning(true);sText("Opening Google Maps in a browser window - please don't close it...");renderFind();
  }catch(e){alertBox("Couldn't start the search",e.message)}
}
window.onPy=function(m){
  const e=m.e,d=m.d||{};
  if(e==="progress")progress(d);
  else if(e==="lead"){if(S.scope==="current"&&d.search!==S.current)return;if(d.status!=="none"||S.find.some(x=>x.id===d.id))return;S.find.push(d);renderFind()}
  else if(e==="refresh")reload();
  else if(e==="sync"){S.sync=d;renderSync();if(d.state==="synced"&&!(S.people||[]).length)api("get_people").then(p=>{S.people=p||[]}).catch(()=>{})}
  else if(e==="auth_changed"){api("boot").then(b=>{if(b.auth&&b.auth.me){S.me=b.auth.me;applyMe()}}).catch(()=>{})}
  else if(e==="auth_lost"){S.me=null;needLogin(d.why==="deactivated"?"This account has been deactivated. Ask an administrator.":"Your session ended. Please sign in again.").then(()=>reload())}
  else if(e==="search_done"){setRunning(false);$("#pfill").style.width=d.stopped?$("#pfill").style.width:"100%";
    const skip=d.skipped?` (${d.skipped} already-called left out - see Called Leads)`:"";
    sText(d.n===0?"No new businesses to call from that search."+skip+" Try a broader area or different wording.":
      (d.stopped?`Stopped. ${d.n} businesses saved.`:`Done: ${d.n} businesses to call, ${d.owners} owner names found.`)+skip+(d.stopped?"":" Missing info shows N/A. Owner names come from website text, so double-check before you call."));
    logNote(d.n?`Search finished: ${d.n} new businesses (${S.current||""})`:"Search finished: no new businesses");
    reload().then(()=>{if(d.n)toast(`${d.n} businesses ready to call`)})}
  else if(e==="search_error"){setRunning(false);sText("");$("#pfill").style.width="0%";reload();alertBox("Search failed",d.error||"Unknown error")}
};
async function exportCsv(called){
  try{const nm=called?"leafline_called_leads.csv":"leafline_leads.csv",path=window.leafline&&window.leafline.saveCsv?await window.leafline.saveCsv(nm):"";if(window.leafline&&!path)return;
    const r=await api("export_csv",called,S.scope,path||"");if(r.ok)toast(`Exported ${r.n} leads`);else if(r.error)toast("Export failed: "+r.error,{bad:1})}catch(e){toast("Export failed: "+e.message,{bad:1})}
}
function renderAll(q){
  profileUI();const n=S.called.length,b=$("#calledBadge");if(b.textContent!==String(n)){b.textContent=n;bump(b)}
  if(S.page==="find"||q)renderFind();
  if(S.page==="called")renderBoard(true);if(S.page==="dash")renderDash(true);if(S.page==="profits")renderProfits(true);if(S.page==="calendar")renderCalendar(true);
  if(S.page==="notes")renderNotes(true);else if(S.dockOpen)loadNotes().then(()=>drawDock(true));
}

/* ---------------- events ---------------- */
document.addEventListener("click",e=>{
  const g=e.target.closest("[data-go]");if(g){go(g.dataset.go);return}
  const bell=$("#bell");if(!e.target.closest("#bell")&&!e.target.closest("#bellBtn"))bell.classList.remove("on");
});
$("#bellBtn").onclick=()=>{const b=$("#bell");b.classList.toggle("on");if(b.classList.contains("on")){S.unread=0;renderBell()}};
$("#userBtn").onclick=()=>go("account");$("#ringBtn").onclick=()=>go("account");
$("#ringBtn").onkeydown=e=>{if(e.key==="Enter")go("account")};
$("#fplus").onclick=async()=>{await go("find");setTimeout(()=>$("#fType").focus(),250)};
$("#goBtn").onclick=startSearch;
["fCountry","fState","fCity","fType"].forEach(i=>$("#"+i).addEventListener("keydown",e=>{if(e.key==="Enter")startSearch()}));
$("#scope").onchange=async e=>{S.scope=e.target.value;S.active=null;S.sel.clear();lastDetail=null;await reload()};
$("#sort").onchange=e=>{S.sort=e.target.value;renderFind()};
$("#fExport").onclick=()=>exportCsv(false);
$("#openOnly").onclick=e=>{S.openOnly=!S.openOnly;e.currentTarget.classList.toggle("on",S.openOnly);renderFind()};
$("#allChk").onclick=()=>{const a=visibleFind(),all=a.length&&a.every(l=>S.sel.has(l.id));a.forEach(l=>all?S.sel.delete(l.id):S.sel.add(l.id));renderFind()};
$("#list").addEventListener("click",e=>{
  const li=e.target.closest(".li");if(!li)return;const id=li.dataset.id;
  if(e.target.closest(".chk")){S.sel.has(id)?S.sel.delete(id):S.sel.add(id);renderFind();return}
  if(S.active!==id){saveDetail(true);S.active=id;lastDetail=null;renderFind()}
});
$("#list").addEventListener("keydown",e=>{
  const li=e.target.closest(".li");if(!li)return;
  if(e.key==="Enter"||e.key===" "){if(!e.target.closest(".chk")){e.preventDefault();li.click()}}
  if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();const n=e.key==="ArrowDown"?li.nextElementSibling:li.previousElementSibling;if(n&&n.classList.contains("li")){n.focus();n.click()}}
});
$("#detail").addEventListener("click",e=>{
  const l=S.find.find(x=>x.id===S.active);if(!l)return;
  if(e.target.closest("#dCopy"))copyText(l.phone);
  else if(e.target.closest("#dSite"))api("open_site",l.id).catch(()=>{});
  else if(e.target.closest("#dSave"))saveDetail(false);
  else{const m=e.target.closest("[data-mark]");if(m)markLeads(m.dataset.mark)}
});
$("#detail").addEventListener("focusout",e=>{if(e.target.id==="dOwner"||e.target.id==="dNotes")saveDetail(true)});
$("#gq").addEventListener("input",e=>{S.q=e.target.value.trim();if(S.page==="dash"||S.page==="account"||S.page==="profits"||S.page==="calendar")go("find");renderFind();if(S.page==="called")renderBoard(true)});
document.addEventListener("keydown",e=>{if(e.key==="/"&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)){e.preventDefault();$("#gq").focus()}});
window.addEventListener("resize",movePills);
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&S.ready)reload()});
setInterval(()=>{if(S.ready&&!document.hidden&&!S.running)reload()},180000);  /* keeps "open now" fresh while the app stays open */

/* ---------------- team dashboard ---------------- */
function tmTime(iso){try{const d=new Date(iso),t=d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});return d.toDateString()===new Date().toDateString()?t:d.toLocaleDateString([],{month:"short",day:"numeric"})+" "+t}catch(e){return""}}
/* ---------------- call streaks ----------------
   A streak grows by one for every workday someone reaches the team's daily call target (Admin > daily targets).
   Weekends never break a streak; reaching the target on a weekend counts as a bonus day.
   Today never breaks it either: until midnight it still counts from yesterday. */
const STREAK=[[3,"#FFD60A","Spark"],[5,"#FF9F1C","Heating up"],[10,"#E8590C","On fire"],[15,"#E5383B","Blazing"],[20,"#A4161A","Inferno"],[30,"#A855F7","Electric"],[45,"#6B21A8","Legendary"],[60,"#3B82F6","Blue flame"]];
const STK={memo:{},at:-1};
const STREAK_GOAL=25;                       /* calls in a day that keep a streak going */
function streakGoal(){return STREAK_GOAL}
function streakTier(n){let t=-1;STREAK.forEach((x,i)=>{if(n>=x[0])t=i});return t}
function streakOf(pid){
  const d=B.data;if(!d||!d.stats||!pid)return null;
  const goal=streakGoal(),key=pid+"|"+goal;if(STK.at!==B.at){STK.memo={};STK.at=B.at}if(STK.memo[key])return STK.memo[key];
  const calls={};d.stats.forEach(r=>{if(r.employee_id===pid)calls[r.day]=(calls[r.day]||0)+(+r.calls||0)});
  const today=d.today||isoDay(new Date()),days=Object.keys(calls).filter(k=>(calls[k]||0)>=goal).sort();
  const wkend=k=>{const x=new Date(k+"T12:00:00").getDay();return x===0||x===6};
  let cur=0,best=0;
  if(days.length)for(let k=days[0],i=0;k<=today&&i<4000;k=dayShift(k,1),i++){
    if((calls[k]||0)>=goal){cur++;if(cur>best)best=cur}else if(k!==today&&!wkend(k))cur=0}
  return STK.memo[key]={n:cur,best,goal,today:calls[today]||0,doneToday:(calls[today]||0)>=goal,tier:streakTier(cur)};
}
function streakTip(s){const t=STREAK[s.tier];return `${s.n}-day call streak${t?" · "+t[2]:""} · ${s.doneToday?"today's "+s.goal+" calls done ✓":s.today+" of "+s.goal+" calls today"} · best ${s.best}`}
function streakChip(pid,o={}){const s=streakOf(pid);if(!s)return "";
  if(!s.n)return o.zero?`<span class="stk none${o.big?" big":""}" title="No call streak yet. ${s.goal} calls on a workday starts one.">${ic("flame")}0</span>`:"";
  const t=STREAK[s.tier],c=t?t[1]:"";
  return `<span class="stk${t?"":" low"}${o.big?" big":""}"${t?` style="--sc:${c};--st:${ink(c)}"`:""} title="${esc(streakTip(s))}" aria-label="${esc(streakTip(s))}">${ic("flame")}${s.n}</span>`}
function streakBar(n){
  const seg=100/STREAK.length;let fill=0;
  for(let i=0;i<STREAK.length;i++){const lo=i?STREAK[i-1][0]:0,hi=STREAK[i][0];if(n>=hi)fill+=seg;else{fill+=seg*Math.max(0,(n-lo)/(hi-lo));break}}
  const grad=`linear-gradient(90deg,${STREAK[0][1]} 0%,${STREAK.map((t,i)=>`${t[1]} ${((i+1)*seg).toFixed(2)}%`).join(",")})`,nx=STREAK.findIndex(t=>n<t[0]);
  return `<div class="stk-bar" role="img" aria-label="${n} day streak; milestones ${STREAK.map(t=>t[0]).join(", ")}"><div class="stk-track"><i style="--w:${(100-fill).toFixed(2)}%;background:${grad}"></i></div>
    ${STREAK.map((t,i)=>`<span class="stk-m${n>=t[0]?" on":i===nx?" next":""}" style="left:${((i+1)*seg).toFixed(2)}%;--sc:${t[1]};--st:${ink(t[1])}" title="${t[0]} days · ${t[2]}">${t[0]}</span>`).join("")}</div>`}
/* each Team card gets its own streak bar, right under the person's latest activity */
const STK_SEEN=new Set();
function paintStreaks(){
  const pg=$("#pg-team");if(!pg)return;
  $$("[data-stk]",pg).forEach(el=>{const pid=el.dataset.stk,s=streakOf(pid);
    if(!s){el.innerHTML=`<div class="stk-cap"><span class="muted">Loading streak…</span></div>`;return}
    const t=STREAK[s.tier];
    el.innerHTML=`<div class="stk-cap"><span style="${t?`color:${t[1]};font-weight:800`:""}">${ic("flame")}</span><span class="${s.doneToday?"ok":""}">${s.n?`${s.n}-day streak${t?" · "+esc(t[2]):""}`:"No streak yet"} · ${s.doneToday?`today's ${s.goal} calls done ✓`:`${num(s.today)}/${s.goal} calls today`}</span><small>best ${s.best}</small></div>${streakBar(s.n)}`;
    el.title=`Reach ${s.goal} calls on a workday to keep the streak going. Weekends never break it; reaching it on a weekend is a bonus day.`;
    if(!STK_SEEN.has(pid)&&!REDUCE){STK_SEEN.add(pid);const i=$(".stk-track i",el);i.classList.add("go");requestAnimationFrame(()=>requestAnimationFrame(()=>i.classList.remove("go")))}else STK_SEEN.add(pid)});
  hydrateIcons(pg);
}
async function renderTeam(){
  const pg=$("#pg-team");let t;
  try{t=await api("get_team")}catch(e){t={ok:false,error:"The app engine did not respond."}}
  if(S.page!=="team")return;
  if(t.ok){S.team=t;if(t.people)S.people=t.people.map(p=>({id:p.id,display_name:p.name,role:p.role,active:true,avatar:p.avatar||"",avatar_url:(p.media||{}).avatar_url||""}))}
  const d=S.team;
  if(!d){pg.innerHTML=`<div class="card empty" style="margin-top:40px"><b>Team numbers aren't available</b>${esc(t.error||"")}</div>`;return}
  const T=d.targets,tot=d.totals,mk=(l,v,g)=>`<div class="tm-tile"><span>${l}</span><b>${num(v)}</b>${g?`<small>of ${num(g)} target</small><div class="tm-bar"><i style="width:${Math.min(100,Math.round(100*v/Math.max(1,g)))}%"></i></div>`:""}</div>`;
  const max=Math.max(1,...d.series.map(x=>x.calls)),W=(a,b)=>["calls","connections","meetings","sales"].map(k=>{const x=a[k],y=b[k],df=x-y;return `<td>${num(x)}</td>`}).join("");
  pg.innerHTML=`<div class="tm">
   ${d.stale?`<div class="stale">You're offline. Showing the last numbers loaded${d.fetched?" at "+esc(d.fetched):""}.</div>`:""}
   <div class="tm-tiles">${mk("Calls today",tot.calls,T.calls)}${mk("Connections",tot.connections,T.connections)}${mk("Prospects contacted",tot.prospects)}${mk("Meetings booked",tot.meetings,T.meetings)}${mk("Sales",tot.sales,T.sales)}
    <div class="tm-tile"><span>Revenue closed today</span><b>${usd(d.revenue_today)}</b><small>${num(d.deals_today)} deal${d.deals_today===1?"":"s"} (upfront)</small></div></div>
   ${d.people.some(p=>freshThought(p.ext))?`<div class="card tm-th"><h3>Thoughts of the day</h3>${d.people.filter(p=>freshThought(p.ext)).map(p=>`<div class="th-i">${avHTML(p.name,p.avatar,p.media)}<div><q>${esc(p.ext.thought)}</q><small>${esc(p.name)}${p.ext.mood?" "+esc(p.ext.mood):""}</small></div></div>`).join("")}</div>`:""}
   <div class="tm-people">${d.people.map(p=>`<div class="card tm-p ${S.me&&S.me.id===p.id?"me":""}" data-pid="${esc(p.id)}" style="--acc:${okAccent((p.ext||{}).accent)||"transparent"}">
     <h3>${avHTML(p.name,p.avatar,p.media)}${esc(p.name)}${(p.ext||{}).mood?` <span>${esc(p.ext.mood)}</span>`:""}${streakChip(p.id)}<span class="role">${p.role==="admin"?"Admin":"Rep"}</span><span class="st ${p.online?"on":""}"><i></i>${p.online?"Online":"Offline"}</span></h3>
     ${bdgSlot(p.id,8)}${(p.ext||{}).title?`<div class="psub">${esc(p.ext.title)}</div>`:""}${(p.ext||{}).bio?`<div class="pbio">${esc(p.ext.bio)}</div>`:""}${freshThought(p.ext)?`<div class="pth">“${esc(p.ext.thought)}”</div>`:""}
     <div class="nums"><div><b>${p.today.calls}</b><span>Calls</span></div><div><b>${p.today.connections}</b><span>Connected</span></div><div><b>${p.today.prospects}</b><span>Prospects</span></div><div><b>${p.today.meetings}</b><span>Meetings</span></div><div><b>${p.today.sales}</b><span>Sales</span></div>${d.tasks_enabled?`<div><b>${p.today.tasks||0}</b><span>Tasks done</span></div>`:""}</div>
     <div class="tm-bar" title="${p.progress}% of the daily call target"><i style="width:${Math.min(100,p.progress)}%"></i></div>
     <div class="last">${p.last?esc(p.last.text)+" · "+esc(tmTime(p.last.at)):"No activity yet."}</div>
     <div class="tm-stkc" data-stk="${esc(p.id)}"></div></div>`).join("")}</div>
   <div class="tm-2">
    <div class="card tm-card"><h3>Last ${d.series.length} days · team calls</h3>
     ${barChart({labels:d.series.map(x=>x.day.slice(8)),hi:d.series.findIndex(x=>x.day===d.today),h:200,still:true,aria:"Team calls per day",series:[{v:d.series.map(x=>x.calls),c:"b0",name:"Calls"},{v:d.series.map(x=>x.meetings),c:"b1",name:"Meetings"}],tips:d.series.map(x=>`${dayFmt(x.day)}: ${num(x.calls)} calls · ${num(x.meetings)} meetings · ${num(x.sales)} sales`)})}
     <table><tr><th></th><th>Calls</th><th>Connected</th><th>Meetings</th><th>Sales</th></tr><tr><td>This week</td>${W(d.week,d.last_week)}</tr><tr><td>Last week</td>${W(d.last_week,d.week)}</tr></table></div>
    <div class="card tm-card"><h3>Activity</h3><div class="tm-feed">${d.activity.length?d.activity.map(a=>`<div>${esc(a.text)}<small>${esc(tmTime(a.at))}</small></div>`).join(""):"<div>Nothing yet today.</div>"}</div></div>
   </div>
   </div>`;
  hydrateIcons(pg);paintStreaks();ensureBoard().then(()=>{if(S.page==="team")paintStreaks()});
  $$("[data-pid]",pg).forEach(c=>c.onclick=()=>personModal(d.people.find(x=>x.id===c.dataset.pid)));
}
setInterval(()=>{if(S.ready&&S.page==="team"&&!document.hidden)renderTeam()},8000);
setInterval(()=>{if(!S.ready||document.hidden||!S.me)return;if(S.page==="board")ensureBoard(true).then(()=>{if(S.page==="board")drawRanks(false)});else ensureBoard()},60000);
setInterval(()=>{if(S.ready&&S.page==="posts"&&!document.hidden)loadPosts(false)},20000);

/* ---------------- accounts + sync ---------------- */
let loginWait=null;
function showLogin(msg){dropLens();$("#pwForm").style.display="none";$("#lgForm").style.display="";$("#lgErr").textContent=msg||"";$("#login").classList.add("on");setTimeout(()=>$("#lgUser").focus(),60)}
function needLogin(msg){showLogin(msg);return new Promise(r=>{loginWait=r})}
function needPw(){dropLens();$("#lgForm").style.display="none";$("#pwForm").style.display="";$("#pwErr").textContent="";$("#login").classList.add("on");setTimeout(()=>$("#pwNew").focus(),60);return new Promise(r=>{loginWait=r})}
function applyMe(){if(!S.me)return;const adm=S.me.role==="admin";["navAdmin","fnAdmin"].forEach(i=>{const e=$("#"+i);if(e)e.style.display=adm?"":"none"});setTimeout(movePills,30);S.profile=S.profile||{};S.profile.name=S.me.display_name;S.profile.role=S.me.role==="admin"?"Administrator":"Employee";profileUI();if(S.page==="account")renderAccount()}
function renderSync(){
  const s=S.sync||{state:"signed_out"},b=$("#syncBtn");if(!b)return;
  const t={synced:"Synced",syncing:"Syncing...",offline:"Offline"+(s.pending?" · "+s.pending+" waiting":""),error:"Sync problem",attention:(s.blocked||0)+" need attention",signed_out:"Signed out"}[s.state]||"Sync";
  b.className="sync "+s.state;$("#syncTx").textContent=t;
  b.title=s.state==="synced"?"Everything is saved to the shared database. Last sync "+(s.last_ok||""):s.state==="offline"?"No connection. Your changes are saved on this computer and will upload automatically.":(s.error||"");
}
async function afterLogin(){applyMe();B.data=null;B.badges={};loadNotes().then(()=>{applyDock()});if(S.me&&S.me.must_change_password)await needPw();ensureBoard(true);setTimeout(pollPosts,1500)}
$("#lgForm").addEventListener("submit",async e=>{
  e.preventDefault();const u=$("#lgUser").value.trim(),p=$("#lgPass").value,btn=$("#lgGo");
  if(!u||!p){$("#lgErr").textContent="Enter your username and password.";return}
  btn.disabled=true;btn.textContent="Signing in...";let r;
  try{r=await api("sign_in",u,p)}catch(x){r={ok:false,error:"The app engine did not respond."}}
  btn.disabled=false;btn.textContent="Sign in";
  if(!r.ok){$("#lgErr").textContent=r.error;$("#lgPass").value="";return}
  const fr=$("#lgMark").getBoundingClientRect();hideApp();
  $("#lgPass").value="";S.me=r.me;$("#login").classList.remove("on");await afterLogin();
  if(S.ready){profileUI();flyToAvatar(fr)}else S.flyFrom=fr;
  const w=loginWait;loginWait=null;w&&w();
});
$("#pwForm").addEventListener("submit",async e=>{
  e.preventDefault();const a=$("#pwNew").value,b2=$("#pwNew2").value,btn=$("#pwGo");
  if(a!==b2){$("#pwErr").textContent="The two passwords don't match.";return}
  btn.disabled=true;let r;try{r=await api("change_password",a)}catch(x){r={ok:false,error:"The app engine did not respond."}}btn.disabled=false;
  if(!r.ok){$("#pwErr").textContent=r.error;return}
  S.me=r.me;$("#pwNew").value=$("#pwNew2").value="";$("#login").classList.remove("on");toast("Password changed.");
  const w=loginWait;loginWait=null;w&&w();
});
$("#outBtn").addEventListener("click",async()=>{
  const r=await api("sign_out");
  if(!r.ok){toast(r.pending+" change"+(r.pending===1?"":"s")+" not uploaded yet. Reconnect, wait for Synced, then sign out.",{bad:true,ms:6000});return}
  S.me=null;await needLogin();await reload();
});
$("#syncBtn").addEventListener("click",async()=>{
  const s=S.sync||{};if(s.blocked){await api("sync_retry");toast("Retrying the changes that were stuck...");return}
  toast(s.state==="synced"?"All changes are saved to the shared database.":s.state==="offline"?"Offline. Changes are kept on this computer and upload when you reconnect.":(s.error||"Syncing..."));
});

/* =====================================================================
   LEAFLINE 11: themes, intro, leaderboard, badges, announcements, media
   ===================================================================== */
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const EASE={out:"cubic-bezier(.22,1,.36,1)",spring:"cubic-bezier(.34,1.32,.64,1)",io:"cubic-bezier(.65,0,.35,1)",in:"cubic-bezier(.55,0,.75,.2)"};
const LOGO=document.querySelector("#introLogo svg.mk")?document.querySelector("#introLogo svg.mk").outerHTML.replace(/lgA/g,"lgF"):"";

/* ---------- pictures: animated original from Storage, still copy as fallback ---------- */
const MEDIA_OK=/^https?:\/\/[A-Za-z0-9.:-]+\/storage\/v1\/object\/public\/media\/[0-9a-f-]{36}\/[A-Za-z0-9._-]{1,80}$/;
const safeMedia=u=>(typeof u==="string"&&u.length<400&&MEDIA_OK.test(u))?u:"";
function avSrc(img,media){const still=safeImg(img),anim=safeMedia(media&&media.avatar_url);return {src:(!REDUCE&&anim)||still||anim,still}}
window.lfImgErr=function(im){const f=im.dataset.f;if(f&&im.getAttribute("src")!==f){im.dataset.f="";im.src=f}else im.remove()};
function imgTag(src,still){return src?`<img class="fade" src="${esc(src)}" alt="" decoding="async" data-f="${still&&still!==src?esc(still):""}" onload="this.classList.add('ok')" onerror="lfImgErr(this)">`:""}
function bannerOf(p){const m=(p&&p.media)||{},anim=safeMedia(m.banner_url),still=safeBanner(p&&p.ext&&p.ext.banner)||safeBanner(p&&p.banner);
  return {src:(!REDUCE&&anim)||still||anim,still,pos:Number.isFinite(+m.banner_pos)&&m.banner_pos!==""&&m.banner_pos!=null?Math.max(0,Math.min(100,+m.banner_pos)):50}}
function bannerHTML(p,cls){const b=bannerOf(p);return b.src?`<div class="pban has-img ${cls||""}" style="--bp:${b.pos}%">${imgTag(b.src,b.still)}</div>`:""}
function imgReady(src,ms){return new Promise(r=>{if(!src)return r(false);const im=new Image(),t=setTimeout(()=>r(false),ms||1500);im.onload=()=>{clearTimeout(t);r(true)};im.onerror=()=>{clearTimeout(t);r(false)};im.src=src})}

/* ---------- themes + the liquid glass control ---------- */
const THEMES=[["forest","Forest","linear-gradient(150deg,#7BEBAE,#2FBF71 55%,#17301F)"],["emerald","Emerald","linear-gradient(150deg,#97F3D6,#22BF8E 55%,#123327)"],["midnight","Midnight","linear-gradient(150deg,#A6EEC5,#1E3A2A 45%,#060908)"]];
const themeNow=()=>document.documentElement.dataset.theme||"forest";
function setTheme(t,anim,save){
  if(!THEMES.some(x=>x[0]===t))t="forest";
  const root=document.documentElement,apply=()=>{if(t==="forest")delete root.dataset.theme;else root.dataset.theme=t;paintLgt()};
  try{localStorage.setItem("lf_theme",t)}catch(e){}
  if(save&&S.ready)setP("theme",t);
  if(t===themeNow()){paintLgt();return}
  if(anim&&!REDUCE&&document.startViewTransition){try{document.startViewTransition(apply);return}catch(e){}}
  if(anim&&!REDUCE){root.classList.add("theming");apply();setTimeout(()=>root.classList.remove("theming"),680)}else apply();
}
function paintLgt(){
  const cur=themeNow();
  $$("[data-lgt]").forEach(el=>{
    if(!el.dataset.built){
      el.innerHTML='<span class="drop"></span>'+THEMES.map(([k,n,g])=>`<button type="button" role="radio" data-th="${k}" aria-label="${n} theme" title="${n} theme"><i style="background:${g}"></i></button>`).join("");
      el.dataset.built=1;
      $$("button",el).forEach(b=>{b.onclick=e=>{e.stopPropagation();setTheme(b.dataset.th,true,true)}});
      el.addEventListener("pointerdown",()=>el.classList.add("press"));["pointerup","pointerleave","pointercancel"].forEach(x=>el.addEventListener(x,()=>el.classList.remove("press")));
    }
    let on=null;$$("button",el).forEach(b=>{const y=b.dataset.th===cur;b.classList.toggle("on",y);b.setAttribute("aria-checked",y);if(y)on=b});
    const d=$(".drop",el);if(on&&d){d.style.left=on.offsetLeft+"px";d.style.width=on.offsetWidth+"px"}
  });
}

/* ---------- phone: "More" sheet ---------- */
const PAGES=[["dash","home","Home"],["team","users","Team"],["board","trophy","Leaderboard"],["posts","mega","Announcements"],["msgs","chat","Messages"],["find","search","Find Leads"],["called","phone","Called Leads"],["calendar","cal","Calendar"],["calls","log","Call Log"],["notes","note","Notes"],["profits","dollar","Profits"],["admin","shield","Admin"],["account","gear","Settings"]];
function openSheet(){
  const sh=$("#msheet"),adm=S.me&&S.me.role==="admin";
  $("#sheetGrid").innerHTML=PAGES.filter(p=>p[0]!=="admin"||adm).map(([k,i,n])=>`<button data-go="${k}" class="${S.page===k?"on":""}" aria-label="${n}">${ic(i)}${n==="Announcements"?`<span class="lgl">${n}</span><span class="sht">News</span>`:`<span>${n}</span>`}${k==="posts"&&S.unreadPosts?`<span class="nb">${S.unreadPosts}</span>`:""}</button>`).join("");
  sh.classList.add("on");sh.setAttribute("aria-hidden","false");paintLgt();requestAnimationFrame(()=>requestAnimationFrame(()=>{sh.classList.add("show");paintLgt()}));
}
function closeSheet(){const sh=$("#msheet");if(!sh.classList.contains("on"))return;sh.classList.remove("show");sh.setAttribute("aria-hidden","true");setTimeout(()=>{if(!sh.classList.contains("show"))sh.classList.remove("on")},460)}
$("#fmore").onclick=e=>{e.stopPropagation();openSheet()};
$("#msheet").addEventListener("click",e=>{if(e.target.closest("[data-close]"))closeSheet()});
$("#sheetBell").onclick=()=>{closeSheet();setTimeout(()=>{const b=$("#bell");b.classList.add("on");S.unread=0;renderBell()},200)};
$("#sheetOut").onclick=()=>{closeSheet();$("#outBtn").click()};
$("#mAvBtn").onclick=()=>go("account");

/* ---------- intro: logo -> press -> flies top-left -> becomes your picture ---------- */
const INTRO={el:$("#intro"),on:!!$("#intro"),t0:performance.now(),skip:!!navigator.webdriver||/[?&]nointro\b/.test(location.search)};
if(INTRO.skip&&INTRO.el){INTRO.el.remove();INTRO.on=false}
function introProgress(f){const c=$("#introPg");if(c)c.style.strokeDashoffset=String(Math.max(0,1-Math.min(1,f)))}
function introDrop(){if(INTRO.el){INTRO.el.remove()}INTRO.on=false}
async function introGate(){
  if(!INTRO.on)return;
  introProgress(1);await sleep(Math.max(0,1700-(performance.now()-INTRO.t0)));
  const el=INTRO.el,lg=$("#introLogo");el.classList.add("ready");if(S.me&&!S.me.must_change_password)makeLens();
  $("#introTx").textContent=matchMedia("(hover:none)").matches?"Tap to enter":"Click to enter";
  lg.tabIndex=0;lg.setAttribute("aria-disabled","false");try{lg.focus({preventScroll:true})}catch(e){}
  await new Promise(res=>{const goIn=e=>{if(e.type==="keydown"&&e.key!=="Enter"&&e.key!==" ")return;e.preventDefault();lg.removeEventListener("click",goIn);document.removeEventListener("keydown",goIn);res()};
    lg.addEventListener("click",goIn);document.addEventListener("keydown",goIn)});
}
async function introLeave(to){
  if(!INTRO.on)return;INTRO.on=false;S.animating=true;setTimeout(()=>{S.animating=false},2600);
  const el=INTRO.el,lg=$("#introLogo"),from=lg.getBoundingClientRect();
  if(REDUCE){el.classList.add("gone");setTimeout(()=>el.remove(),650);return}
  lg.style.visibility="hidden";
  if(to==="login"){el.classList.add("gone");setTimeout(()=>el.remove(),700);await flyLogo(from,$("#lgMark"));return}
  await flyToAvatar(from,el);
}
function makeFlyer(r){const f=document.createElement("div");f.className="flyer";Object.assign(f.style,{left:r.left+"px",top:r.top+"px",width:r.width+"px",height:r.height+"px"});return f}
const raf2=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
async function flyLogo(from,toEl){
  if(!toEl)return;const to=toEl.getBoundingClientRect();if(!to.width)return;
  const f=makeFlyer(from);f.innerHTML=`<div class="fl-in"><div class="fl-sq"></div><div class="fl-logo">${LOGO}</div></div>`;document.body.appendChild(f);toEl.style.visibility="hidden";
  const k=to.width/from.width;await raf2();
  const a=f.animate([{transform:"none"},{transform:`translate(${to.left-from.left}px,${to.top-from.top}px) scale(${k})`}],{duration:820,easing:EASE.io,fill:"forwards"});
  try{await a.finished}catch(e){}
  toEl.style.visibility="";f.remove();
}
/* Signature start-up: the logo travels to where your picture lives, then the app opens outward from that spot
   like a lens while the logo turns into your picture. Everything that moves is a GPU transform or fade. */
let LENS=null;
const avTarget=()=>[$("#mAv"),$("#sideAv")].find(e=>e&&e.getBoundingClientRect().width>0);
function makeLens(){
  if(LENS)return LENS;setTimeout(()=>{if(LENS&&!LENS.flying){dropLens();$$(".flyer").forEach(f=>f.remove())}},15000);const t=avTarget();if(!t||REDUCE||INTRO.skip)return null;
  const r=t.getBoundingClientRect(),d=Math.max(8,r.width),cx=r.left+r.width/2,cy=r.top+r.height/2,R=Math.ceil(Math.hypot(Math.max(cx,innerWidth-cx),Math.max(cy,innerHeight-cy)))+80;
  /* screen-sized cover with a round hole at the picture; scaling it around the hole opens the app.
     The texture is only ever the size of the screen, so big monitors stay as smooth as phones. */
  const el=document.createElement("div");el.className="lens";el.style.transformOrigin=`${cx}px ${cy}px`;
  el.style.background=`radial-gradient(circle at ${cx}px ${cy}px,transparent ${d/2}px,var(--bg) ${d/2+1}px)`;
  const box=(g)=>`left:${cx-d/2-g}px;top:${cy-d/2-g}px;width:${d+2*g}px;height:${d+2*g}px`;
  el.innerHTML=`<b style="${box(4)}"></b><i style="${box(1)}"></i>`;
  document.body.appendChild(el);LENS={el,d,R,cx,cy};return LENS;
}
function dropLens(){if(LENS){LENS.el.remove();LENS=null}}
function hideApp(){makeLens()}
async function flyToAvatar(from,cover){
  const fade=()=>{if(cover&&cover.isConnected){cover.classList.add("gone");setTimeout(()=>cover.remove(),650)}};
  const tgt=avTarget();
  if(!tgt||!from||REDUCE||INTRO.skip){dropLens();fade();return}
  const L=makeLens(),to=tgt.getBoundingClientRect();if(L)L.flying=true;
  const me=S.me||{},{src}=avSrc(me.avatar,me.media),ok=src?await imgReady(src,1500):false;
  const f=makeFlyer(from),nm=me.display_name||(S.profile&&S.profile.name)||"";
  f.innerHTML=`<div class="fl-glow"></div><div class="fl-in"><div class="fl-sq"></div><div class="fl-ci"></div><div class="fl-logo">${LOGO}</div><div class="fl-logo fl-bl" style="opacity:0">${LOGO}</div><div class="fl-av fl-bl">${ok?"":esc(nm?initials(nm):"LF")}</div><div class="fl-av">${ok?"":esc(nm?initials(nm):"LF")}</div></div><div class="fl-ring"></div>`;
  const inn=$(".fl-in",f),[avB,av]=$$(".fl-av",f),[lgo,lgoB]=$$(".fl-logo",f),glow=$(".fl-glow",f),ring=$(".fl-ring",f);
  [avB,av].forEach(x=>{if(ok)x.style.backgroundImage=`url("${src}")`;else x.style.background=`linear-gradient(150deg,${(S.profile&&S.profile.color)||"#4ADE8B"}66,var(--av-bg))`;x.style.fontSize=Math.round(from.width*.34)+"px"});
  document.body.appendChild(f);tgt.style.opacity="0";
  if(cover){const t=$(".ib0",cover);t&&t.animate([{opacity:1},{opacity:0}],{duration:260,easing:EASE.out,fill:"forwards"});
    cover.animate([{opacity:1},{opacity:0}],{duration:520,delay:120,easing:EASE.out,fill:"forwards"}).finished.then(()=>cover.remove(),()=>cover.remove())}
  await raf2();                                   /* let the browser settle the new layers before moving anything */
  const dx=to.left-from.left,dy=to.top-from.top,k=to.width/from.width,mk=(1+k)/2,T1=950;
  /* 1. travel: glide left first, then rise into the picture's spot */
  const a=f.animate([{transform:"none"},{transform:`translate(${dx*.82}px,${dy*.3}px) scale(${mk})`,offset:.55},{transform:`translate(${dx}px,${dy}px) scale(${k})`}],{duration:T1,easing:EASE.io,fill:"forwards"});
  /* rounded square -> circle: two ready-made shapes crossfade (no repainting while moving) */
  $(".fl-sq",f).animate([{opacity:1},{opacity:1,offset:.45},{opacity:0}],{duration:T1,easing:EASE.io,fill:"forwards"});
  $(".fl-ci",f).animate([{opacity:0},{opacity:0,offset:.4},{opacity:1}],{duration:T1,easing:EASE.io,fill:"forwards"});
  try{await a.finished}catch(e){}
  /* 2. the app opens outward from the picture while the logo becomes the picture */
  const D=950,end=`translate(${dx}px,${dy}px) scale(${k})`;
  if(L){$("b",L.el).animate([{opacity:1},{opacity:0}],{duration:120,fill:"forwards"});$("i",L.el).animate([{opacity:0},{opacity:1,offset:.15},{opacity:.6}],{duration:D,easing:EASE.out,fill:"forwards"});
    L.el.animate([{transform:"scale(1)"},{transform:`scale(${(2*L.R/L.d).toFixed(3)})`}],{duration:D,easing:"cubic-bezier(.6,0,.2,1)",fill:"forwards"})}
  f.animate([{transform:end},{transform:`translate(${dx}px,${dy}px) scale(${k*1.22})`,offset:.35},{transform:end}],{duration:760,easing:EASE.spring,fill:"forwards"});
  /* logo spins away going soft; picture arrives soft then sharpens (pre-blurred copies crossfade: no per-frame blur) */
  const out={duration:420,easing:EASE.out,fill:"forwards"},inn2={duration:520,delay:120,easing:EASE.out,fill:"forwards"};
  lgo.animate([{opacity:1,transform:"none"},{opacity:0,transform:"rotate(-24deg) scale(.6)"}],out);
  lgoB.animate([{opacity:0,transform:"none"},{opacity:.9,transform:"rotate(-12deg) scale(.8)",offset:.4},{opacity:0,transform:"rotate(-24deg) scale(.6)"}],out);
  avB.animate([{opacity:0,transform:"scale(1.4)"},{opacity:1,transform:"scale(1.15)",offset:.45},{opacity:0,transform:"none"}],inn2);
  av.animate([{opacity:0,transform:"scale(1.4)"},{opacity:0,transform:"scale(1.15)",offset:.3},{opacity:1,transform:"none"}],inn2);
  glow.animate([{opacity:0,transform:"scale(.6)"},{opacity:1,transform:"scale(1.15)",offset:.35},{opacity:0,transform:"scale(1.6)"}],{duration:900,easing:EASE.out,fill:"forwards"});
  ring.animate([{opacity:.9,transform:"scale(1)"},{opacity:0,transform:"scale(1.35)"}],{duration:800,delay:150,easing:EASE.out,fill:"forwards"});
  await new Promise(r=>setTimeout(r,D));
  tgt.style.opacity="";dropLens();fade();
  const rg=tgt.closest(".ring,.mav");rg&&rg.animate([{transform:"scale(1)"},{transform:"scale(1.06)",offset:.4},{transform:"scale(1)"}],{duration:600,easing:EASE.spring});
  f.animate([{opacity:1},{opacity:0}],{duration:200,easing:EASE.out}).finished.then(()=>f.remove(),()=>f.remove());
}

/* ---------- leaderboard data, ranking and badges (computed here from real numbers) ---------- */
const B={data:null,at:0,loading:null,badges:{}};
async function ensureBoard(force){
  if(!S.me)return null;
  if(!force&&B.data&&Date.now()-B.at<60000)return B.data;
  if(B.loading)return B.loading;
  B.loading=api("get_board").then(r=>{if(r&&r.ok){B.data=r;B.at=Date.now();B.badges=computeBadges(r);paintBadges()}else if(r&&!B.data)B.err=r.error;return B.data}).catch(()=>B.data).finally(()=>{B.loading=null});
  return B.loading;
}
function dealPays(d,upto){
  const out=[],up=+d.upfront||0,mo=+d.monthly||0,n=+d.months||0;
  /* with the 7th database update, only payments someone confirmed count as money made */
  const cs="confirmed" in d?new Set(String(d.confirmed||"").split(",")):null,ok=(ds,k)=>!cs||cs.has(ds+":"+k);
  if(d.closed_at&&up>0&&d.closed_at<=upto&&ok(d.closed_at,"upfront"))out.push([d.closed_at,up]);
  const f=d.first_bill||d.closed_at;
  if(f&&mo>0){const [y,m,dd]=f.split("-").map(Number);
    for(let k=0;n===0||k<n;k++){const t=y*12+(m-1)+k,yy=Math.floor(t/12),mm=t%12,dim=new Date(yy,mm+1,0).getDate();
      const ds=`${yy}-${String(mm+1).padStart(2,"0")}-${String(Math.min(dd,dim)).padStart(2,"0")}`;if(ds>upto)break;if(ok(ds,"monthly"))out.push([ds,mo])}}
  return out;
}
const dayShift=(iso,n)=>{const d=new Date(iso+"T00:00:00");d.setDate(d.getDate()+n);return isoDay(d)};
function rangeOf(per,today){if(per==="all")return ["2000-01-01",today];const t=new Date(today+"T00:00:00");if(per==="week")t.setDate(t.getDate()-((t.getDay()+6)%7));else t.setDate(1);return [isoDay(t),today]}
function tally(d,from,to){
  const m={};d.people.forEach(p=>m[p.id]={calls:0,meetings:0,money:0,sales:0,days:{}});
  for(const r of d.stats||[]){const x=m[r.employee_id],day=String(r.day).slice(0,10);if(!x||day<from||day>to)continue;
    x.calls+=+r.calls||0;x.meetings+=+r.meetings||0;x.sales+=+r.sales||0;x.days[day]=(x.days[day]||0)+(+r.calls||0)}
  for(const dl of d.deals||[]){const x=m[dl.owner_id];if(!x)continue;for(const [ds,a] of dealPays(dl,to))if(ds>=from)x.money+=a}
  for(const k in m)m[k].money=Math.round(m[k].money*100)/100;
  return m;
}
const BADGES={
  mvp:{n:"Team MVP",d:"Holds two or more of Top Caller, Meeting Machine and Revenue Champion",i:"crown"},
  top_caller:{n:"Top Caller",d:"Most calls in the last 7 days",i:"phone"},
  meetings:{n:"Meeting Machine",d:"Most meetings booked in the last 7 days",i:"cal"},
  revenue:{n:"Revenue Champion",d:"Most money collected in the last 30 days",i:"dollar"},
  consistency:{n:"Consistency King",d:"Made calls on each of the last 5 weekdays",i:"flame"},
  rising:{n:"Rising Star",d:"At least 20 calls this week and 25% more than the week before",i:"rocket"},
  closer:{n:"Deal Closer",d:"Closed a deal in the last 30 days",i:"hand"},
  century:{n:"Century Club",d:"100 or more calls in a single day (last 30 days)",i:"bolt"}};
function computeBadges(d){
  const T=d.today,ids=d.people.map(p=>p.id),w=tally(d,dayShift(T,-6),T),pw=tally(d,dayShift(T,-13),dayShift(T,-7)),m30=tally(d,dayShift(T,-29),T),out={};
  ids.forEach(i=>out[i]=[]);
  const top=(t,k,b)=>{const mx=Math.max(0,...ids.map(i=>t[i][k]));if(mx>0)ids.forEach(i=>{if(t[i][k]===mx)out[i].push(b)})};
  top(w,"calls","top_caller");top(w,"meetings","meetings");top(m30,"money","revenue");
  const wds=[];{const x=new Date(T+"T00:00:00");while(wds.length<5){x.setDate(x.getDate()-1);if(x.getDay()%6)wds.push(isoDay(x))}}
  const from30=dayShift(T,-29);
  ids.forEach(i=>{
    if(wds.every(x=>(m30[i].days[x]||0)>0))out[i].push("consistency");
    const a=w[i].calls,b=pw[i].calls;if(a>=20&&a>=b*1.25&&a>b)out[i].push("rising");
    if((d.deals||[]).some(x=>x.owner_id===i&&x.closed_at&&x.closed_at>=from30&&x.closed_at<=T))out[i].push("closer");
    if(Object.values(m30[i].days).some(v=>v>=100))out[i].push("century");
    if(["top_caller","meetings","revenue"].filter(b=>out[i].includes(b)).length>=2)out[i].unshift("mvp");
  });
  return out;
}
function badgeHTML(pid,max,big){
  const l=(B.badges[pid]||[]).slice(0,max||8);
  return l.map(k=>{const b=BADGES[k];return `<span class="badge-i b-${k}${big?" lg":""}" title="${esc(b.n)}: ${esc(b.d)}" role="img" aria-label="${esc(b.n)}">${ic(b.i)}${big?esc(b.n):""}</span>`}).join("");
}
const bdgSlot=(pid,max,big)=>`<span class="bdg" data-bdg="${esc(pid)}" data-max="${max||8}"${big?' data-big="1"':""}>${badgeHTML(pid,max,big)}</span>`;
function paintBadges(root){$$("[data-bdg]",root||document).forEach(e=>{const h=badgeHTML(e.dataset.bdg,+e.dataset.max||8,!!e.dataset.big);if(e.innerHTML!==h)e.innerHTML=h})}
function personById(id){
  /* use whichever copy has the picture: leaderboard data, Team page data, or the people list */
  const b=B.data&&B.data.people.find(p=>p.id===id),t=S.team&&S.team.people&&S.team.people.find(p=>p.id===id);
  if(b||t){const x={...(t||{}),...(b||{})};if(!x.avatar)x.avatar=(t&&t.avatar)||(b&&b.avatar)||"";
    const m={...((t&&t.media)||{}),...((b&&b.media)||{})};x.media=m;x.ext={...((t&&t.ext)||{}),...((b&&b.ext)||{})};
    if(!x.avatar&&!m.avatar_url){const q=(S.people||[]).find(p=>p.id===id);if(q&&q.avatar)x.avatar=q.avatar}
    return x}
  const p=(S.people||[]).find(x=>x.id===id);if(p)return {id,name:p.display_name||p.username||"Teammate",role:p.role,avatar:p.avatar||"",ext:{},media:{avatar_url:p.avatar_url||""}};
  if(S.me&&S.me.id===id)return {id,name:S.me.display_name,role:S.me.role,avatar:S.me.avatar,ext:S.me.ext||{},media:S.me.media||{}};
  return {id,name:"Former teammate",role:"",avatar:"",ext:{},media:{}};
}

/* ---------- leaderboard page ---------- */
const LBM=[["calls","phone","Most Calls","calls"],["meetings","cal","Most Meetings","meetings"],["money","dollar","Most Money Made","collected"]];
const LBP=[["week","This week"],["month","This month"],["all","All time"]];
function moveSeg(seg){const on=$("button.on",seg),k=$(".sk",seg);if(on&&k){k.style.left=on.offsetLeft+"px";k.style.width=on.offsetWidth+"px"}}
async function renderRanks(q){
  const pg=$("#pg-board");
  if(!pg.dataset.built){
    pg.innerHTML=`<div class="lbd"><div class="lb-head pop"><div class="lseg" id="lbM" role="tablist" aria-label="Ranking">${'<span class="sk"></span>'}${LBM.map(([k,i,n])=>`<button role="tab" data-m="${k}">${ic(i)}<span class="lbx">${n}</span><span class="lbs">${n.replace("Most ","").replace(" Made","")}</span></button>`).join("")}</div>
      <div class="lseg sm" id="lbP" aria-label="Period"><span class="sk"></span>${LBP.map(([k,n])=>`<button data-p="${k}">${n}</button>`).join("")}</div></div><div id="lbBody"><div class="empty" style="margin-top:60px"><div class="spin"></div><b>Loading the leaderboard...</b></div></div></div>`;
    pg.dataset.built=1;
    $$("#lbM button").forEach(b=>b.onclick=()=>{setP("lbMetric",b.dataset.m);drawRanks(true)});
    $$("#lbP button").forEach(b=>b.onclick=()=>{setP("lbPeriod",b.dataset.p);drawRanks(true)});
    hydrateIcons(pg);
  }
  syncSegs();
  if(!B.data){const d=await ensureBoard(true);if(S.page!=="board")return;if(!d){$("#lbBody").innerHTML=`<div class="card empty" style="margin-top:30px"><b>The leaderboard isn't available</b>${esc(B.err||"Check your connection and try again.")}</div>`;return}}
  else if(!q)ensureBoard(true).then(()=>{if(S.page==="board")drawRanks(false)});
  drawRanks(!q);
}
function syncSegs(){const m=getP("lbMetric","calls"),p=getP("lbPeriod","week");$$("#lbM button").forEach(b=>b.classList.toggle("on",b.dataset.m===m));$$("#lbP button").forEach(b=>b.classList.toggle("on",b.dataset.p===p));$$("#pg-board .lseg").forEach(moveSeg)}
function drawRanks(anim){
  const body=$("#lbBody"),d=B.data;if(!body||!d)return;syncSegs();
  const metric=getP("lbMetric","calls"),per=getP("lbPeriod","week"),[f,t]=rangeOf(per,d.today),tl=tally(d,f,t),def=LBM.find(x=>x[0]===metric);
  const rows=d.people.map(p=>({p,v:tl[p.id][metric]})).sort((a,b)=>b.v-a.v||a.p.name.localeCompare(b.p.name));
  rows.forEach((r,i)=>{r.rank=i&&rows[i-1].v===r.v?rows[i-1].rank:i+1});
  const sig=JSON.stringify([metric,per,rows.map(r=>[r.p.id,r.v]),B.badges,d.people.map(p=>[p.avatar.length,p.media])]);
  if(!anim&&body.dataset.sig===sig)return;body.dataset.sig=sig;
  const old={};if(!REDUCE)$$("[data-lbid]",body).forEach(e=>{old[e.dataset.lbid]=e.getBoundingClientRect()});
  const fmt=v=>metric==="money"?usd(v):num(v),mx=Math.max(1,...rows.map(r=>r.v)),me=S.me&&S.me.id,top=rows.slice(0,3),rest=rows.slice(3),any=rows.some(r=>r.v>0);
  const pod=(r,cls)=>r?`<div class="pod ${cls}" data-lbid="${esc(r.p.id)}" data-pid="${esc(r.p.id)}" tabindex="0" role="button" aria-label="${esc(r.p.name)}, rank ${r.rank}">${cls==="p1"?`<span class="crown">${ic("crown")}</span>`:`<span class="rk">#${r.rank}</span>`}
     ${avHTML(r.p.name,r.p.avatar,r.p.media)}<h4>${esc(r.p.name)}</h4><div class="v">${metric==="money"?"$":""}<span class="vl" data-n="${r.v}" data-d="${metric==="money"&&!Number.isInteger(r.v)?2:0}" data-s="">${metric==="money"?fmt(r.v).slice(1):fmt(r.v)}</span></div><div class="u">${def[3]}</div>${bdgSlot(r.p.id,4)}<div class="base"></div></div>`:"<div></div>";
  body.innerHTML=`${d.stale?`<div class="tm stale" style="padding:0;margin-bottom:10px"><div class="stale">You're offline. Showing the numbers from ${esc(d.fetched||"earlier")}.</div></div>`:""}
    ${any?"":`<div class="lb-note" style="margin:6px 0 14px">No ${def[3]} recorded ${per==="all"?"yet":"in this period yet"}. Rankings fill in as the team works.</div>`}
    <div class="pods">${pod(top[1],"p2")}${pod(top[0],"p1")}${pod(top[2],"p3")}</div>
    <div class="lbl" style="margin-top:18px">${rest.map(r=>`<div class="lbr${r.p.id===me?" me":""}" data-lbid="${esc(r.p.id)}" data-pid="${esc(r.p.id)}" tabindex="0" role="button"><span class="rk">#${r.rank}</span>${avHTML(r.p.name,r.p.avatar,r.p.media)}
      <div class="nm"><b>${esc(r.p.name)}</b>${bdgSlot(r.p.id,5)}</div><div class="lbar"><i data-w="${Math.round(100*r.v/mx)}"></i></div><span class="v">${fmt(r.v)}</span></div>`).join("")}</div>
    <div class="lb-note" style="margin-top:12px">${metric==="money"?"Money = payments collected on deals each person owns (upfront + monthly payments that are due). ":metric==="meetings"?"Meetings = calls logged with the result “Meeting booked”. ":"Calls = every call logged in the app. "}Updated ${esc(d.fetched||"just now")}.</div>
    <div class="card lb-badges pop" style="margin-top:18px"><h3>Badges</h3><div class="note">Earned automatically from the team's real numbers. They update every few minutes.</div>
     <div class="grid">${Object.entries(BADGES).map(([k,b])=>{const who=d.people.filter(p=>(B.badges[p.id]||[]).includes(k));return `<div class="bi"><span class="badge-i b-${k}">${ic(b.i)}</span><div style="min-width:0"><b>${esc(b.n)}</b><small>${esc(b.d)}</small></div><div class="who">${who.slice(0,4).map(p=>avHTML(p.name,p.avatar,p.media)).join("")}</div></div>`}).join("")}</div></div>`;
  hydrateIcons(body);
  $$("[data-pid]",body).forEach(e=>{e.onclick=()=>personModal(personFull(e.dataset.pid));e.onkeydown=k=>{if(k.key==="Enter")e.click()}});
  requestAnimationFrame(()=>$$(".lbr .lbar i",body).forEach(i=>i.style.width=i.dataset.w+"%"));
  if(!REDUCE)$$("[data-lbid]",body).forEach(e=>{const o=old[e.dataset.lbid];if(!o)return;const n=e.getBoundingClientRect(),dx=o.left-n.left,dy=o.top-n.top;
    if(Math.abs(dx)>1||Math.abs(dy)>1)e.animate([{transform:`translate(${dx}px,${dy}px)`},{transform:"none"}],{duration:620,easing:EASE.spring})});
  if(anim)$$(".pod .vl",body).forEach(e=>countTo(e,+e.dataset.n,+e.dataset.d,"",800));
}
function personFull(id){const p=personById(id),t=S.team&&S.team.people&&S.team.people.find(x=>x.id===id);return t?{...p,...t,media:t.media||p.media}:p}

/* ---------- announcements & ideas ---------- */
const KINDS={announcement:["Announcement","mega"],idea:["Idea","bulb"],update:["Update","spark"]};
const EMO=["👍","🔥","💡","🎉","❤️"];
const P={list:null,cmo:new Set(),kind:"announcement"};
function ago(iso){const s=(Date.now()-new Date(iso).getTime())/1000;if(!isFinite(s))return"";if(s<60)return"just now";if(s<3600)return Math.floor(s/60)+"m ago";if(s<86400)return Math.floor(s/3600)+"h ago";if(s<604800)return Math.floor(s/86400)+"d ago";return new Date(iso).toLocaleDateString("en-US",{month:"short",day:"numeric"})}
async function renderPosts(){
  const pg=$("#pg-posts");
  if(!pg.dataset.built){
    pg.innerHTML=`<div class="ps"><div class="card ps-comp pop" id="psComp">
      <div class="row"><input class="inp" id="psTitle" data-mention maxlength="120" placeholder="Share an announcement, an idea or an update..." aria-label="Post title"></div>
      <div class="more"><div><textarea class="inp" id="psBody" data-mention maxlength="4000" rows="4" placeholder="Add the details (optional). Type @ to tag someone, like @James" aria-label="Post details"></textarea>
       <div class="acts"><div class="ps-f" id="psKind">${Object.entries(KINDS).map(([k,[n,i]])=>`<button type="button" class="chip${k==="announcement"?" on":""}" data-k="${k}">${ic(i)}${n}</button>`).join("")}</div>
       <div style="display:flex;gap:8px;flex:1;justify-content:flex-end"><button class="btn" id="psCancel">Cancel</button><button class="btn pri" id="psPost">${ic("send")}Post</button></div></div></div></div></div>
     <div class="ps-f pop" id="psFilter"><button class="chip" data-f="all">All</button>${Object.entries(KINDS).map(([k,[n,i]])=>`<button class="chip" data-f="${k}">${ic(i)}${n}s</button>`).join("")}</div>
     <div id="psList"><div class="empty" style="margin-top:50px"><div class="spin"></div><b>Loading the board...</b></div></div></div>`;
    pg.dataset.built=1;hydrateIcons(pg);
    const comp=$("#psComp"),open=()=>comp.classList.add("open");
    $("#psTitle").addEventListener("focus",open);$("#psTitle").addEventListener("input",open);
    $("#psCancel").onclick=()=>{$("#psTitle").value=$("#psBody").value="";comp.classList.remove("open")};
    $$("#psKind .chip").forEach(b=>b.onclick=()=>{P.kind=b.dataset.k;$$("#psKind .chip").forEach(x=>x.classList.toggle("on",x===b))});
    $("#psPost").onclick=async()=>{const b=$("#psPost");b.disabled=true;
      const r=await api("save_post",{title:$("#psTitle").value,body:$("#psBody").value,kind:P.kind}).catch(e=>({ok:false,error:e.message}));b.disabled=false;
      if(!r.ok)return toast(r.error||"Couldn't post.",{bad:1});
      $("#psTitle").value=$("#psBody").value="";comp.classList.remove("open");toast("Posted to the team");loadPosts(true)};
    $$("#psFilter .chip").forEach(b=>b.onclick=()=>{setP("postFilter",b.dataset.f);drawPosts(true)});
    $("#psList").addEventListener("click",postClick);
    $("#psList").addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.matches(".cadd .inp")){e.preventDefault();e.target.parentElement.querySelector("[data-csend]").click()}});
    wireHover($("#psList"));
  }
  $$("#psFilter .chip").forEach(b=>b.classList.toggle("on",b.dataset.f===getP("postFilter","all")));
  ensureBoard().then(()=>{if(S.page==="posts")drawPosts(false)});
  if(!S.team)api("get_team").then(t=>{if(t&&t.ok){S.team=t;if(S.page==="posts")drawPosts(false)}}).catch(()=>{});
  await loadPosts(false);
}
async function loadPosts(fresh){
  const r=await api("get_posts").catch(e=>({ok:false,error:e.message}));
  if(S.page!=="posts")return r;
  const l=$("#psList");
  if(!r.ok){
    $("#psComp").style.display=r.need_migration?"none":"";
    l.innerHTML=r.need_migration?`<div class="card need"><h3>One more database step</h3><p>The Announcements board, animated pictures and the leaderboard's deal guard need the <b>5th database update</b>. An admin opens Supabase, goes to <b>SQL Editor</b>, pastes the file <code>supabase/migrations/20261107000005_board_posts_media.sql</code> and presses <b>Run</b>. Everything else keeps working until then.</p></div>`
      :`<div class="card empty" style="margin-top:20px"><div class="bub">${ic("mega")}</div><b>${r.offline?"You're offline":"Couldn't load the board"}</b>${esc(r.error||"")}</div>`;
    hydrateIcons(l);return r;
  }
  $("#psComp").style.display="";P.list=r.posts;checkMentions(r.posts);S.unreadMentions=0;markPostsSeen();drawPosts(fresh);return r;
}
function drawPosts(anim){
  const l=$("#psList");if(!l||!P.list)return;$$("#psFilter .chip").forEach(b=>b.classList.toggle("on",b.dataset.f===getP("postFilter","all")));
  const f=getP("postFilter","all"),me=S.me&&S.me.id;
  const ps=P.list.filter(p=>f==="all"||p.kind===f).sort((a,b)=>(b.pinned-a.pinned)||String(b.created_at).localeCompare(String(a.created_at)));
  const sig=JSON.stringify([ps,f,[...P.cmo],B.at,!!S.team]);if(!anim&&l.dataset.sig===sig)return;l.dataset.sig=sig;
  const keep=$$(".cadd .inp",l).reduce((o,i)=>{if(i.value)o[i.dataset.pid]=i.value;return o},{});
  l.innerHTML=ps.length?ps.map(p=>{const a=personById(p.author_id),k=KINDS[p.kind]||KINDS.announcement,ed=p.edited_at?personById(p.edited_by):null;
    return `<article class="card post${anim?" pop":""}${p.pinned?" pinned":""}${P.cmo.has(p.id)?" cmo":""}" data-id="${esc(p.id)}">
     <div class="ph2"><div class="au" data-au="${esc(p.author_id)}" tabindex="0" role="button" aria-label="${esc(a.name)}'s profile">${avHTML(a.name,a.avatar,a.media)}<div style="min-width:0"><b>${esc(a.name)}${bdgSlot(p.author_id,3)}</b><small>${esc(ago(p.created_at))}</small></div></div>
      <div class="kd">${p.pinned?`<span class="ptag">${ic("pin")}Pinned</span>`:""}<span class="ptag ${esc(p.kind)}">${ic(k[1])}${k[0]}</span>
       <div class="pmenu"><button class="ib" data-menu aria-label="Post options">${ic("dots")}</button><div class="mn"><button data-act="edit">${ic("edit")}Edit</button><button data-act="pin">${ic("pin")}${p.pinned?"Unpin":"Pin to top"}</button><button data-act="del" class="dn">${ic("trash")}Delete</button></div></div></div></div>
     <h3>${richText(p.title)}</h3>${p.body?`<div class="bd">${richText(p.body)}</div>`:""}${ed?`<div class="ed">Edited by ${esc(ed.name)} · ${esc(ago(p.edited_at))}</div>`:""}
     <div class="rx">${EMO.map(e=>{const u=(p.reactions||{})[e]||[];return `<button data-rx="${e}" class="${u.includes(me)?"on":""}" aria-label="React ${e}" title="${esc(u.map(x=>personById(x).name).join(", "))}">${e}${u.length?`<span>${u.length}</span>`:""}</button>`}).join("")}
      <button class="cm" data-cm aria-expanded="${P.cmo.has(p.id)}">${ic("chat")}<span>${(p.comments||[]).length?(p.comments.length+" comment"+(p.comments.length===1?"":"s")):"Comment"}</span></button></div>
     <div class="cms"><div>${(p.comments||[]).map(c=>{const ca=personById(c.author_id);return `<div class="cmt" data-cid="${esc(c.id)}">${avHTML(ca.name,ca.avatar,ca.media)}<div class="cb"><b>${esc(ca.name)}</b><small>${esc(ago(c.created_at))}</small><p>${richText(c.body)}</p></div><button class="ib cx" data-cdel aria-label="Delete comment">${ic("trash")}</button></div>`}).join("")}
      <div class="cadd"><input class="inp" data-mention data-pid="${esc(p.id)}" maxlength="1000" placeholder="Write a comment... type @ to tag someone" aria-label="Write a comment"><button class="btn sm pri" data-csend>Send</button></div></div></div></article>`}).join("")
    :`<div class="card empty" style="margin-top:10px"><div class="bub">${ic("mega")}</div><b>${f==="all"?"Nothing posted yet":"No "+KINDS[f][0].toLowerCase()+"s yet"}</b>Share news, wins or ideas for the business with the whole team.</div>`;
  hydrateIcons(l);
  $$(".cadd .inp",l).forEach(i=>{if(keep[i.dataset.pid])i.value=keep[i.dataset.pid]});
}
async function postClick(e){
  const art=e.target.closest(".post");if(!art)return;const id=art.dataset.id,p=(P.list||[]).find(x=>x.id===id);if(!p)return;
  const menu=e.target.closest("[data-menu]");if(menu){e.stopPropagation();const m=menu.parentElement,on=!m.classList.contains("on");$$(".pmenu.on").forEach(x=>x.classList.remove("on"));m.classList.toggle("on",on);return}
  const act=e.target.closest("[data-act]");
  if(act){act.closest(".pmenu").classList.remove("on");const a=act.dataset.act;
    if(a==="edit")return editPost(p);
    if(a==="pin"){const r=await api("post_op","pin",id,!p.pinned);if(!r.ok)return toast(r.error||"Couldn't pin.",{bad:1});toast(p.pinned?"Unpinned":"Pinned to the top");return loadPosts(true)}
    if(a==="del")return openModal(`<h2>Delete this post?</h2><p class="muted" style="margin:10px 0 20px;line-height:1.55">"${esc(p.title)}" and its comments will be removed for everyone. This can't be undone.</p><div style="display:flex;gap:10px;justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn stop" data-ok>Delete</button></div>`,(ov,close)=>{
      $("[data-x]",ov).onclick=close;$("[data-ok]",ov).onclick=async()=>{const r=await api("post_op","delete",id);close();if(!r.ok)return toast(r.error||"Couldn't delete.",{bad:1});
        if(!REDUCE)await art.animate([{opacity:1,transform:"none"},{opacity:0,transform:"translateX(-24px) scale(.97)"}],{duration:280,easing:EASE.in,fill:"forwards"}).finished.catch(()=>{});toast("Post deleted");loadPosts(true)}});
  }
  const rx=e.target.closest("[data-rx]");
  if(rx){const me=S.me&&S.me.id,u=(p.reactions=p.reactions||{})[rx.dataset.rx]=(p.reactions[rx.dataset.rx]||[]);const had=u.includes(me);
    if(had)u.splice(u.indexOf(me),1);else u.push(me);drawPosts(false);const nb=$(`.post[data-id="${id}"] [data-rx="${rx.dataset.rx}"]`);if(nb&&!had&&!REDUCE){nb.classList.add("pulse");setTimeout(()=>nb.classList.remove("pulse"),450)}
    const r=await api("post_op","react",id,rx.dataset.rx);if(!r.ok)toast(r.error||"Couldn't react.",{bad:1});loadPosts(false);return}
  if(e.target.closest("[data-cm]")){P.cmo.has(id)?P.cmo.delete(id):P.cmo.add(id);art.classList.toggle("cmo",P.cmo.has(id));e.target.closest("[data-cm]").setAttribute("aria-expanded",P.cmo.has(id));if(P.cmo.has(id))setTimeout(()=>{const i=$(".cadd .inp",art);i&&i.focus({preventScroll:true})},260);return}
  if(e.target.closest("[data-csend]")){const i=$(".cadd .inp",art),v=i.value.trim();if(!v)return;i.disabled=true;const r=await api("post_op","comment",id,v);i.disabled=false;if(!r.ok)return toast(r.error||"Couldn't comment.",{bad:1});i.value="";P.cmo.add(id);loadPosts(true);return}
  const cd=e.target.closest("[data-cdel]");if(cd){const r=await api("post_op","uncomment",cd.closest(".cmt").dataset.cid);if(!r.ok)return toast(r.error||"Couldn't delete.",{bad:1});loadPosts(true);return}
}
document.addEventListener("click",e=>{if(!e.target.closest(".pmenu"))$$(".pmenu.on").forEach(x=>x.classList.remove("on"))});
function editPost(p){
  let kind=p.kind;
  openModal(`<h2>Edit post</h2><p class="muted" style="margin:4px 0 14px;font-size:13px">Anyone on the team can edit posts. Your name is shown as the last editor.</p>
    <label class="l" for="epT">Title</label><input class="inp" id="epT" data-mention maxlength="120" value="${esc(p.title)}" style="width:100%">
    <label class="l" for="epB" style="margin-top:12px">Details</label><textarea class="inp" id="epB" data-mention maxlength="4000" rows="6" style="width:100%">${esc(p.body)}</textarea>
    <div class="ps-f" id="epK" style="margin-top:12px">${Object.entries(KINDS).map(([k,[n,i]])=>`<button type="button" class="chip${k===kind?" on":""}" data-k="${k}">${ic(i)}${n}</button>`).join("")}</div>
    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>Save</button></div>`,(ov,close)=>{
    $$("#epK .chip",ov).forEach(b=>b.onclick=()=>{kind=b.dataset.k;$$("#epK .chip",ov).forEach(x=>x.classList.toggle("on",x===b))});
    $("[data-x]",ov).onclick=close;
    $("[data-ok]",ov).onclick=async()=>{const r=await api("save_post",{id:p.id,title:$("#epT",ov).value,body:$("#epB",ov).value,kind});if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1});close();toast("Post updated");loadPosts(true)}});
}
function markPostsSeen(){const n=(P.list||[]).reduce((m,p)=>p.created_at>m?p.created_at:m,"");if(n&&n>getP("postsSeen",""))setP("postsSeen",n);S.unreadPosts=0;paintUnread()}
function paintUnread(){const n=Math.max(S.unreadPosts||0,S.unreadMentions||0),b=$("#postsBadge");if(b){b.textContent=n;b.style.display=n?"":"none"}const d=$("#moreDot");if(d)d.classList.toggle("on",n>0)}
async function pollPosts(){
  if(!S.ready||!S.me||document.hidden||S.page==="posts"||S.animating)return;
  const r=await api("get_posts").catch(()=>null);if(!r||!r.ok)return;
  checkMentions(r.posts);
  const seen=getP("postsSeen",""),me=S.me.id;S.unreadPosts=r.posts.filter(p=>p.created_at>seen&&p.author_id!==me).length;
  if(!seen&&r.posts.length){setP("postsSeen",r.posts[0].created_at);S.unreadPosts=0}
  paintUnread();
}
setInterval(pollPosts,45000);


/* ---------- full banner for anyone (the team list leaves the heavy banner out), cached for 5 minutes ---------- */
const PBAN={};
async function personBanner(pid){
  const c=PBAN[pid];if(c&&Date.now()-c.t<300000)return c.b;
  if(S.me&&pid===S.me.id){const b=bannerOf({ext:S.me.ext,media:S.me.media});return {...b,url:S.me.media&&S.me.media.banner_url}}
  try{const r=await api("get_person",pid);if(r&&r.ok&&r.person){const q=r.person,b=bannerOf({ext:{banner:q.banner},media:{banner_url:q.banner_url,banner_pos:q.banner_pos}});
    const out={...b,url:q.banner_url};PBAN[pid]={t:Date.now(),b:out};return out}}catch(e){}
  return {src:"",still:"",pos:50};
}
/* ---------- @mentions, like Discord: type @ and pick a teammate ---------- */
function mentionPeople(){return teamList().map(([id,name])=>({id,name}))}
function mentionRx(){const ps=mentionPeople().sort((a,b)=>b.name.length-a.name.length);
  return ps.length?{ps,rx:new RegExp("@("+ps.map(p=>p.name.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")+")(?![\\w])","gi")}:null}
/* Text with @Names turned into chips (and everything else escaped). Click a chip to see the profile. */
function richText(t){
  const m=mentionRx(),me=S.me&&S.me.display_name;let out="",last=0;const src=String(t||"");
  if(!m)return esc(src);
  src.replace(m.rx,(all,name,i)=>{const p=m.ps.find(x=>x.name.toLowerCase()===name.toLowerCase());out+=esc(src.slice(last,i))+`<span class="ment${me&&p.name===me?" me":""}" data-au="${esc(p.id)}" tabindex="0" role="button">@${esc(p.name)}</span>`;last=i+all.length;return all});
  return out+esc(src.slice(last));
}
function mentionsMe(t){const m=mentionRx(),me=S.me&&S.me.display_name;if(!m||!me)return false;let hit=false;String(t||"").replace(m.rx,(a,n)=>{if(n.toLowerCase()===me.toLowerCase())hit=true;return a});return hit}
const MP={el:null,inp:null,list:[],i:0,start:-1};
function mpClose(){if(MP.el){MP.el.remove();MP.el=null}MP.inp=null}
function mpPick(p){const el=MP.inp;if(!el||!p)return;const v=el.value,c=el.selectionStart,txt="@"+p.name+" ";
  el.value=v.slice(0,MP.start)+txt+v.slice(c);const pos=MP.start+txt.length;el.setSelectionRange(pos,pos);el.dispatchEvent(new Event("input",{bubbles:true}));mpClose();el.focus()}
function mpDraw(){const el=MP.el;el.innerHTML=MP.list.map((p,i)=>{const f=personById(p.id);return `<button type="button" class="${i===MP.i?"on":""}" data-i="${i}">${avHTML(p.name,f.avatar,f.media)}<span>${esc(p.name)}</span>${S.me&&p.id===S.me.id?'<small>you</small>':""}</button>`}).join("");
  $$("button",el).forEach(b=>{b.onmousedown=e=>{e.preventDefault();mpPick(MP.list[+b.dataset.i])}})}
function mpCheck(el){
  const v=el.value,c=el.selectionStart,m=/(^|[\s(])@([^\s@]{0,24})$/.exec(v.slice(0,c));
  if(!m){if(MP.inp===el)mpClose();return}
  const q=m[2].toLowerCase(),list=mentionPeople().filter(p=>p.name.toLowerCase().startsWith(q)||p.name.toLowerCase().includes(" "+q)).slice(0,6);
  if(!list.length){mpClose();return}
  MP.start=c-m[2].length-1;MP.list=list;MP.i=Math.min(MP.i,list.length-1);
  if(!MP.el||MP.inp!==el){mpClose();MP.el=document.createElement("div");MP.el.className="mpick";MP.el.setAttribute("role","listbox");document.body.appendChild(MP.el);MP.inp=el;MP.i=0}
  mpDraw();const r=el.getBoundingClientRect(),h=MP.el.offsetHeight;let top=r.bottom+6;if(top+h>innerHeight-10)top=Math.max(10,r.top-h-6);
  Object.assign(MP.el.style,{left:Math.max(10,Math.min(innerWidth-MP.el.offsetWidth-10,r.left))+"px",top:top+"px"});
}
document.addEventListener("input",e=>{if(e.target.matches&&e.target.matches("[data-mention]"))mpCheck(e.target)});
document.addEventListener("keydown",e=>{
  if(!MP.el||e.target!==MP.inp)return;
  if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();MP.i=(MP.i+(e.key==="ArrowDown"?1:MP.list.length-1))%MP.list.length;mpDraw()}
  else if(e.key==="Enter"||e.key==="Tab"){e.preventDefault();e.stopImmediatePropagation();mpPick(MP.list[MP.i])}
  else if(e.key==="Escape"){e.stopPropagation();mpClose()}
},true);
document.addEventListener("focusout",e=>{if(e.target===MP.inp)setTimeout(()=>{if(document.activeElement!==MP.inp)mpClose()},120)});
/* Tell me when someone tags me (checked whenever the board loads, and every 90 seconds in the background) */
function checkMentions(posts){
  if(!S.me||!posts)return;const me=S.me.id,seen=getP("mentionSeen","");let newest=seen;const hits=[];
  for(const p of posts){
    if(p.author_id!==me&&p.created_at>seen&&(mentionsMe(p.title)||mentionsMe(p.body)))hits.push({p,who:p.author_id,at:p.created_at,what:"a post"});
    for(const c of p.comments||[])if(c.author_id!==me&&c.created_at>seen&&mentionsMe(c.body))hits.push({p,who:c.author_id,at:c.created_at,what:"a comment"});
    [p.created_at,...(p.comments||[]).map(c=>c.created_at)].forEach(t=>{if(t>newest)newest=t});
  }
  if(!seen){if(newest)setP("mentionSeen",newest);return}
  if(newest>seen)setP("mentionSeen",newest);
  hits.sort((a,b)=>a.at.localeCompare(b.at)).forEach(h=>logNote(`${personById(h.who).name} mentioned you in ${h.what}: "${h.p.title}"`));
  S.unreadMentions=(S.unreadMentions||0)+hits.length;paintUnread();
  if(hits.length){const h=hits[hits.length-1];toast(`${personById(h.who).name} mentioned you${hits.length>1?" (+"+(hits.length-1)+" more)":""}`,{ms:8000,action:{label:"Open",fn:()=>openPost(h.p.id)}})}
}
async function openPost(id){if(S.page!=="posts")await go("posts");const t0=Date.now();
  const find=()=>{const a=$(`.post[data-id="${CSS.escape(id)}"]`);if(a){a.scrollIntoView({behavior:REDUCE?"auto":"smooth",block:"center"});a.animate([{boxShadow:"0 0 0 2px var(--accent),0 0 40px var(--glow)"},{boxShadow:"0 0 0 0 transparent"}],{duration:1600,easing:EASE.out})}else if(Date.now()-t0<5000)setTimeout(find,250)};find()}
/* ---------- floating profile preview (hover on desktop, tap on phones) ---------- */
const HC={el:null,t:null,pid:null,anchor:null};
const TOUCH=matchMedia("(hover:none)").matches;
function wireHover(root){
  root.addEventListener("mouseover",e=>{if(TOUCH)return;const a=e.target.closest("[data-au]");if(!a||a===HC.anchor)return;clearTimeout(HC.t);HC.t=setTimeout(()=>showHover(a,a.dataset.au),260)});
  root.addEventListener("mouseout",e=>{if(TOUCH)return;const a=e.target.closest("[data-au]");if(!a||a.contains(e.relatedTarget))return;clearTimeout(HC.t);HC.t=setTimeout(hideHover,220)});
  root.addEventListener("click",e=>{const a=e.target.closest("[data-au]");if(!a)return;e.stopPropagation();if(TOUCH&&HC.anchor!==a)showHover(a,a.dataset.au);else{hideHover();personModal(personFull(a.dataset.au))}});
  root.addEventListener("keydown",e=>{const a=e.target.closest("[data-au]");if(a&&e.key==="Enter"){hideHover();personModal(personFull(a.dataset.au))}});
}
function showHover(anchor,pid){
  hideHover(true);const p=personFull(pid),ext=p.ext||{},T=B.data?B.data.today:isoDay(new Date()),tl=B.data?tally(B.data,rangeOf("week",T)[0],T)[pid]:null;
  const el=document.createElement("div");el.className="hcard";el.setAttribute("role","dialog");el.setAttribute("aria-label",p.name+"'s profile");
  const bn=bannerOf(p);
  el.innerHTML=`<div class="hb">${bn.src?imgTag(bn.src,bn.still).replace('<img ','<img style="width:100%;height:100%;object-fit:cover;object-position:center '+bn.pos+'%" '):""}</div><div class="hm">${avHTML(p.name,p.avatar,p.media)}
    <h4>${esc(p.name)}${ext.mood?` <span>${esc(ext.mood)}</span>`:""}${streakChip(pid,{zero:true})}</h4><div class="sub">${esc([ext.title,p.role==="admin"?"Admin":p.role?"Rep":""].filter(Boolean).join(" · "))}</div>
    ${bdgSlot(pid,8,false)}${ext.bio?`<p>${esc(ext.bio)}</p>`:""}
    ${tl?`<div class="hs"><div><b>${num(tl.calls)}</b><span>Calls this wk</span></div><div><b>${num(tl.meetings)}</b><span>Meetings</span></div><div><b>${usd(tl.money)}</b><span>Collected</span></div></div>`:""}</div>`;
  document.body.appendChild(el);hydrateIcons(el);HC.el=el;HC.pid=pid;HC.anchor=anchor;
  if(!bn.src||!safeMedia(p.media&&p.media.banner_url))personBanner(pid).then(b=>{if(HC.el!==el||!b.src||(bn.src&&!safeMedia(b.url)))return;const hb=$(".hb",el);
    hb.innerHTML=imgTag(b.src,b.still).replace('<img ','<img style="width:100%;height:100%;object-fit:cover;object-position:center '+b.pos+'%" ')});
  if(!TOUCH){const r=anchor.getBoundingClientRect(),h=el.offsetHeight,w=el.offsetWidth;let top=r.bottom+10;if(top+h>innerHeight-12)top=Math.max(12,r.top-h-10);
    el.style.left=Math.max(12,Math.min(innerWidth-w-12,r.left))+"px";el.style.top=top+"px";
    el.onmouseenter=()=>clearTimeout(HC.t);el.onmouseleave=()=>{HC.t=setTimeout(hideHover,200)}}
  el.onclick=()=>{hideHover();personModal(p)};
  requestAnimationFrame(()=>requestAnimationFrame(()=>el.classList.add("on")));
}
function hideHover(now){const el=HC.el;HC.el=null;HC.anchor=null;if(!el)return;if(now||REDUCE){el.remove();return}el.classList.remove("on");setTimeout(()=>el.remove(),300)}
document.addEventListener("click",e=>{if(HC.el&&!e.target.closest(".hcard")&&!e.target.closest("[data-au]"))hideHover()});
document.addEventListener("scroll",()=>{if(HC.el&&!TOUCH)hideHover()},true);

/* ---------- picture & banner uploads (GIF / WebP / PNG / JPEG / AVIF) ---------- */
const MEDIA_TYPES=/^image\/(gif|webp|png|jpeg|avif)$/;
function readAsDataURL(f){return new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=()=>rej(new Error("Couldn't read that file."));r.readAsDataURL(f)})}
const fmtSize=n=>n>1048576?(n/1048576).toFixed(1)+" MB":Math.max(1,Math.round(n/1024))+" KB";
function mediaDialog(kind,file){
  if(!file)return;
  if(!MEDIA_TYPES.test(file.type))return toast("Use a GIF, WebP, PNG, JPEG or AVIF image.",{bad:1});
  if(file.size>8*1024*1024)return toast(`That file is ${fmtSize(file.size)}. The limit is 8 MB.`,{bad:1});
  const url=URL.createObjectURL(file),av=kind==="avatar",anim=/gif|webp|png|avif/.test(file.type);
  let pos=(S.me&&S.me.media&&+S.me.media.banner_pos>=0)?+S.me.media.banner_pos:50;
  openModal(`<h2>${av?"New profile picture":"New banner"}</h2><div class="mprev"><div class="${av?"pv-av":"pv-bn"}"><img src="${url}" alt="Preview" id="mdImg" style="object-position:center ${pos}%"></div>
    <div class="meta">${esc(file.type.replace("image/","").toUpperCase())} · ${fmtSize(file.size)}${anim?" · animation is kept":""}</div>
    ${av?"":`<label class="l" for="mdPos" style="align-self:stretch;margin:6px 0 0">Banner position</label><input type="range" class="rng" id="mdPos" min="0" max="100" value="${pos}">`}</div>
    <div class="note" style="margin-top:12px">The team sees ${av?"this picture":"this banner"} on the Team page, the leaderboard and announcements. People who turn off animations on their device see a still copy.</div>
    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>Save</button></div>`,(ov,close)=>{
    const done=()=>{URL.revokeObjectURL(url);close()};$("[data-x]",ov).onclick=done;
    const rg=$("#mdPos",ov);if(rg)rg.oninput=()=>{pos=+rg.value;$("#mdImg",ov).style.objectPosition=`center ${pos}%`};
    $("[data-ok]",ov).onclick=async()=>{const b=$("[data-ok]",ov);b.disabled=true;b.textContent="Uploading...";
      try{await saveMedia(kind,file,pos);done()}catch(x){toast(x.message,{bad:1});b.disabled=false;b.textContent="Save"}};
  });
}
async function saveMedia(kind,file,pos){
  const av=kind==="avatar",thumb=av?await pictureFromFile(file):await bannerFromFile(file),data=await readAsDataURL(file);
  let r=await api("upload_media",kind,data,thumb);
  S.me.media=S.me.media||{};
  if(!r.ok){
    if(!/5th database update/.test(r.error||""))throw new Error(r.error||"Upload failed.");
    r=av?await api("set_avatar",thumb):await api("set_profile_ext",{banner:thumb});
    if(!r.ok)throw new Error(r.error||"Couldn't save.");
    if(av)S.me.avatar=thumb;else S.me.ext=r.ext;toast("Saved as a still picture. Animated pictures need the 5th database update.",{ms:6000});
  }else{
    S.me.media[kind+"_url"]=r.url;if(av)S.me.avatar=thumb;else S.me.ext={...(S.me.ext||{}),banner:thumb};
    toast(av?"Profile picture updated":"Banner updated");
  }
  if(!av&&pos!==undefined){S.me.media.banner_pos=pos;api("set_banner_pos",pos).catch(()=>{})}
  B.at=0;profileUI();paintAccountMedia();
}
function paintAccountMedia(){
  if(S.page!=="account"||!S.me)return;const me=S.me,b0=bannerOf({ext:me.ext,media:me.media}),bp=$("#bnPrev");
  if(bp){bp.style.setProperty("--bp",b0.pos+"%");bp.innerHTML=imgTag(b0.src,b0.still);$("#bnDel").style.display=b0.src?"":"none"}
  const idc=$("#pg-account .idc"),old=idc&&$(":scope>.pban",idc);if(idc){const h=bannerHTML({ext:me.ext,media:me.media});if(old)old.remove();if(h)idc.insertAdjacentHTML("afterbegin",h)}
  const d=$("#avDel");if(d)d.style.display=(me.avatar||(me.media&&me.media.avatar_url))?"":"none";
}
async function clearMedia(kind){
  const av=kind==="avatar";await api("clear_media",kind).catch(()=>{});
  const r=av?await api("set_avatar",""):await api("set_profile_ext",{banner:""});
  if(!r.ok)return toast(r.error||"Couldn't remove it.",{bad:1});
  S.me.media=S.me.media||{};S.me.media[kind+"_url"]="";if(av)S.me.avatar="";else S.me.ext=r.ext;
  toast(av?"Photo removed":"Banner removed");profileUI();paintAccountMedia();
}

/* ---------- lead generation: provider-agnostic, OFF by default, zero-spend lock ---------- */
const LEADGEN={
  providers:{
    google_places:{name:"Google Places API",paid:true,ready:false,note:"Not connected. Google needs a billing account and an API key, and charges per request past its monthly free usage, so Leafline keeps it locked."},
    osm_overpass:{name:"OpenStreetMap (Overpass)",paid:false,ready:false,note:"Free and needs no key, but phone numbers and hours are often missing. Not built yet."},
    desktop_maps:{name:"Desktop Google Maps search",paid:false,ready:true,desktop:true,note:"What Find Leads uses today in the Windows app. Free; it runs a browser on your computer."}},
  cfg(){const c=getP("leadgen",null)||{};return {on:!!c.on,provider:this.providers[c.provider]?c.provider:"google_places"}},
  status(){const c=this.cfg(),p=this.providers[c.provider];
    if(!c.on)return {on:false,text:"Off. No requests are made."};
    if(p.paid)return {on:true,text:`On, but ${p.name} stays locked (zero-spend). Nothing is sent.`};
    if(!p.ready)return {on:true,text:`On. ${p.name} is not built yet, so nothing is sent.`};
    if(p.desktop&&window.LF_API)return {on:true,text:`On. ${p.name} only runs in the desktop app.`};
    return {on:true,text:`On. Using ${p.name}.`}},
  async search(){const c=this.cfg(),p=this.providers[c.provider];
    if(!c.on)throw new Error("Lead generation is turned off.");
    if(p.paid)throw new Error("Blocked by the zero-spend lock.");
    if(!p.ready)throw new Error(p.name+" is not connected yet.");
    throw new Error("Use Find Leads in the desktop app.")}
};
function leadgenCard(){
  const c=LEADGEN.cfg(),s=LEADGEN.status();
  return `<div class="card form pop lgen" id="lgenCard"><div class="row"><div><h3>Lead generation</h3><div class="note">Finds new businesses automatically from an online places service, for phones and the website too. Off by default.</div></div>
    <button class="tgl${c.on?" on":""}" id="lgTgl" role="switch" aria-checked="${c.on}" aria-label="Lead generation"></button></div>
    <div class="stt${s.on?" on":""}" id="lgStt"><i></i><span>${esc(s.text)}</span></div>
    <div class="prov">${Object.entries(LEADGEN.providers).map(([k,p])=>`<label><input type="radio" name="lgP" value="${k}"${c.provider===k?" checked":""}><span><b>${esc(p.name)}</b>${p.paid?' <span class="ptag idea" style="height:20px;font-size:10.5px">PAID</span>':""}<small>${esc(p.note)}</small></span></label>`).join("")}</div>
    <div class="note" style="margin-top:12px">Zero-spend lock: Leafline never sends a request to a paid service, even when this is on. Details are in LEAD_GENERATION.md.</div></div>`;
}
function wireLeadgen(root){
  const t=$("#lgTgl",root);if(!t)return;
  const paint=()=>{const c=LEADGEN.cfg(),s=LEADGEN.status();t.classList.toggle("on",c.on);t.setAttribute("aria-checked",c.on);$("#lgStt",root).classList.toggle("on",s.on);$("#lgStt span",root).textContent=s.text;paintLeadgenFind()};
  t.onclick=()=>{const c=LEADGEN.cfg();setP("leadgen",{...c,on:!c.on});paint();toast(!c.on?"Lead generation turned on (still zero-spend)":"Lead generation turned off")};
  $$("input[name=lgP]",root).forEach(i=>i.onchange=()=>{setP("leadgen",{...LEADGEN.cfg(),provider:i.value});paint()});
}
function paintLeadgenFind(){
  const pg=$("#pg-find");if(!pg)return;let c=$("#lgFind");const s=LEADGEN.status();
  if(!s.on||!window.LF_API){c&&c.remove();return}
  if(!c){c=document.createElement("div");c.id="lgFind";c.className="card lgen-card";pg.insertBefore(c,pg.firstChild)}
  c.innerHTML=`<span class="badge-i lg b-rising">${ic("spark")}Lead generation</span><div class="note" style="flex:1">${esc(s.text)}</div><button class="btn sm" data-go="account">Settings</button>`;
}

/* ---------------- boot ---------------- */
async function boot(){
  hydrateIcons();$$(".pop").forEach(e=>io.observe(e));renderBell();paintLgt();introProgress(.08);
  if(!window.LF_API){try{const es=new EventSource("/events?t="+encodeURIComponent(TOKEN));es.onmessage=e=>{try{window.onPy(JSON.parse(e.data))}catch(x){}}}catch(e){}}
  const pageFromHash=(location.hash||"").slice(1);
  let b=null;for(let i=0;i<80&&!b;i++){try{b=await api("boot")}catch(e){await new Promise(r=>setTimeout(r,150))}}
  if(!b){introDrop();$("#pg-dash").innerHTML='<div class="card empty" style="margin-top:40px"><b>The app engine did not start.</b>Close the app and open it again.</div>';$("#pg-dash").classList.add("on");return}
  S.profile=b.profile;S.stats=b.stats;S.find=b.find;S.called=b.called;S.deals=b.deals||[];S.current=b.current;S.dbPath=b.db_path;S.scope=b.current?"current":"all";$("#scope").value=S.scope;
  if(b.running)setRunning(true);applyCountry(false);profileUI();
  S.sync=b.auth&&b.auth.sync;S.me=b.auth&&b.auth.me;S.people=(b.auth&&b.auth.people)||[];renderSync();
  introProgress(.4);
  if(!S.me||S.me.must_change_password){await introGate();if(!S.me)showLogin();else{applyMe();$("#lgForm").style.display="none";$("#pwForm").style.display="";$("#login").classList.add("on")}await introLeave("login");
    if(!S.me)await needLogin();else await needPw()}
  else applyMe();
  try{S.prefs=await api("get_prefs")||{}}catch(e){S.prefs={}}
  if(getP("theme",""))setTheme(getP("theme","forest"),false,false);
  introProgress(.6);
  S.dockOpen=!!getP("dockOpen",false);S.dockId=getP("dockId",0);
  if(S.me){try{await loadNotes()}catch(e){}}
  S.ready=true;initUpdates().then(()=>{if(UP&&UP.platform!=="web"&&UPS.state==="ready")paintUpd()});
  if(window.LF_API){const sl=$("#sText");if(sl)sl.textContent="New businesses are found in the Leafline desktop app and show up here automatically."}
  const start=TITLES[pageFromHash]?pageFromHash:"dash";S.page="__";$("#title").textContent=TITLES[start];
  await go(start,true);renderAll(true);applyDock();if(S.page!=="find")renderFind();
  introProgress(.85);
  if(S.me){ensureBoard(true);setTimeout(pollPosts,6000);const a=avSrc(S.me.avatar,S.me.media);if(a.src&&INTRO.on)await imgReady(a.src,2500)}
  if(INTRO.on){await introGate();await introLeave("avatar")}
  else if(S.flyFrom){const f=S.flyFrom;S.flyFrom=null;flyToAvatar(f)}
  else dropLens();
  setTimeout(movePills,60);
}
boot();
</script>
</body>
</html>
'''

import leafline_messages_ui as _msgui
UI_HTML = _msgui.inject(UI_HTML)          # Messages (team chat): styles + page code live in leafline_messages_ui.py


API_METHODS = ("boot", "get_profile", "save_profile", "get_find", "get_called", "stats", "mark", "save_lead",
               "open_site", "export_csv", "search", "stop", "get_deals", "save_deal", "delete_deal", "confirm_payment", "sb_rpc", "sb_storage", "sb_session", "sb_group_picture", "get_calendar", "save_event", "delete_event", "set_meeting",
               "sign_in", "sign_out", "change_password", "sync_status", "sync_retry", "sync_details", "get_team", "get_people",
               "set_event_done", "get_notes", "save_note", "delete_note", "get_calls", "log_call",
               "admin_people", "admin_update", "admin_targets", "admin_export", "get_prefs", "set_pref", "set_avatar", "set_profile_ext", "get_person",
               "upload_media", "clear_media", "set_banner_pos", "get_board", "get_posts", "save_post", "post_op", "get_credit", "set_credit")
FONT_FALLBACK = {"__FONT_REG__": "fonts/Inter-Regular.ttf", "__FONT_BOLD__": "fonts/Inter-Bold.ttf"}


def make_handler(api, port, token):
    page = UI_HTML
    for k, v in FONT_FALLBACK.items():
        page = page.replace(k, v)
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok(self):  # only our own window (right host header + secret token) may talk to the engine
            q = self.path.partition("?")[2]
            t = dict(x.partition("=")[::2] for x in q.split("&") if x).get("t", "")
            from urllib.parse import unquote
            return self.headers.get("Host", "") in hosts and hmac.compare_digest(unquote(t), token)

        def _send(self, code, body, ctype="application/json"):
            b = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            route = self.path.partition("?")[0]
            if not self._ok():
                return self._send(403, json.dumps({"error": "Forbidden"}))
            if route == "/":
                return self._send(200, page, "text/html")
            if route == "/ping":
                return self._send(200, '{"ok": true}')
            if route == "/events":
                q = queue.Queue()
                with api._lock:
                    api._subs.append(q)
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(b": open\n\n")
                    self.wfile.flush()
                    while True:
                        try:
                            self.wfile.write(b"data: " + q.get(timeout=15).encode("utf-8") + b"\n\n")
                        except queue.Empty:
                            self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                except Exception:
                    pass
                finally:
                    with api._lock:
                        if q in api._subs:
                            api._subs.remove(q)
                return
            self._send(404, json.dumps({"error": "Not found"}))

        def do_POST(self):
            route = self.path.partition("?")[0]
            if not self._ok():
                return self._send(403, json.dumps({"error": "Forbidden"}))
            name = route[5:] if route.startswith("/api/") else ""
            if name not in API_METHODS:
                return self._send(404, json.dumps({"error": "Unknown call"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                args = json.loads(self.rfile.read(n) or b"[]")
                out = getattr(api, name)(*(args if isinstance(args, list) else []))
                self._send(200, json.dumps(out if out is not None else {}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e) or e.__class__.__name__}))
    return H


def main():
    port = int(os.environ.get("LEAFLINE_PORT") or 0)
    token = os.environ.get("LEAFLINE_TOKEN") or secrets.token_urlsafe(24)
    api = Api()
    # bind first (port 0 = any free port), then build the handler that needs the real port number
    server = ThreadingHTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.RequestHandlerClass = make_handler(api, port, token)
    server.daemon_threads = True
    print(f"READY http://127.0.0.1:{port}/?t={token}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        api._stop.set()


if __name__ == "__main__":
    main()
