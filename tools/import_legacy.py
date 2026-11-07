#!/usr/bin/env python3
"""Import a legacy Leafline leads_v2.db into the shared Supabase database.

SAFE BY DEFAULT: without --apply nothing is sent anywhere; the file is opened read-only
and a report is written. The source database is never modified.

  python import_legacy.py "C:\\path\\leads_v2.db"                 # dry run + report
  python import_legacy.py "C:\\path\\leads_v2.db" --apply         # real import
  python import_legacy.py ... --apply --owner gio                 # attribute records to an employee

Needs for --apply: SUPABASE_URL and SUPABASE_SECRET_KEY in tools/.env (admin PC only, never in the app).
Before writing anything it copies the source file into ./legacy_backups (hash-verified) and, if the shared
database already holds data, exports that too. Existing shared rows are never overwritten.
Dates in the old file have no timezone; they are read as America/Toronto (--tz to change).
"""
import argparse, hashlib, json, os, re, shutil, sqlite3, subprocess, sys
import _env  # noqa: F401
from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_OUTCOME = {"orange": "no_answer", "red": "not_interested", "yellow": "interested", "green": "meeting_booked"}


def digits10(p): return re.sub(r"\D", "", p or "")[-10:]


def ts(s, tz):
    """'2026-11-06 16:31[:56]' -> ISO with offset, or None. Never guesses on bad input."""
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try: return datetime.strptime(s, f).replace(tzinfo=tz).isoformat()
        except ValueError: pass
    return None


def day(s):
    s = (s or "").strip()
    try: datetime.strptime(s, "%Y-%m-%d"); return s
    except ValueError: return None


def build(path, tz, owner, sha):
    uri = "file:" + path.replace("\\", "/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True); db.row_factory = sqlite3.Row
    if db.execute("pragma integrity_check").fetchone()[0] != "ok": sys.exit("Source database failed integrity check; aborting.")
    tables = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
    rep = {"source_rows": {}, "customers_imported": 0, "calls_derived_from_status": 0, "activities_imported": 0,
           "calendar_events_imported": 0, "notes_imported": 0, "deals_imported": 0, "duplicates_identified": 0,
           "records_not_migrated": 0, "problems": [], "needs_manual_follow_up": [], "owner": owner or "UNASSIGNED"}
    leads, calls, dups, deals, events, bad = [], [], [], [], [], []
    seen_id, seen_phone = {}, {}
    rows = [dict(r) for r in db.execute("select * from leads")]
    rows.sort(key=lambda r: ((r.get("status") or "none") == "none", not r.get("called_at")))  # worked copies are kept over untouched ones
    rep["source_rows"]["leads"] = len(rows)
    for r in rows:
        raw = dict(r)
        if not (r.get("name") or "").strip():
            bad.append({"table": "leads", "id": r.get("id"), "why": "no business name"}); continue
        key = digits10(r.get("phone")) or None
        why = None
        if r["id"] in seen_id: why = "same id as " + r["id"]
        elif key and key in seen_phone: why = "same phone as lead " + seen_phone[key]
        if why:
            dups.append({"kept_lead_id": seen_id.get(r["id"]) and r["id"] or seen_phone.get(key), "reason": why, "original": raw}); continue
        seen_id[r["id"]] = r["id"]
        if key: seen_phone[key] = r["id"]
        called, meet = ts(r.get("called_at"), tz), ts(r.get("meeting_at"), tz)
        if r.get("called_at") and not called: rep["problems"].append(f"unreadable called_at on {r['id']}: {r['called_at']!r}")
        leads.append({"id": r["id"], "name": r["name"], "phone": r.get("phone") or "", "owner_name": r.get("owner") or "N/A",
            "email": r.get("email") or "N/A", "rating": r.get("rating") or "N/A", "reviews": r.get("reviews") or "N/A",
            "website": r.get("website") or "N/A", "address": r.get("address") or "N/A", "search": r.get("search"),
            "btype": r.get("btype") or "", "hours": r.get("hours") or "", "status": r.get("status") or "none",
            "notes": r.get("notes") or "", "enriched": bool(r.get("enriched")), "added_at": ts(r.get("added_at"), tz),
            "called_at": called, "meeting_at": meet, "source": "legacy", "raw": raw})
        if called and r.get("status") in STATUS_OUTCOME:
            # The old app kept only the LAST result per lead, not a call history. One derived record per lead,
            # flagged source='legacy_status' so it is never counted as a real call in team statistics.
            calls.append({"lead_id": r["id"], "phone": r.get("phone") or "", "started_at": called,
                          "outcome": STATUS_OUTCOME[r["status"]], "notes": r.get("notes") or "", "source": "legacy_status"})
        if r.get("status") == "green" and not meet:
            rep["needs_manual_follow_up"].append(f"'{r['name']}' is marked meeting set up but has no meeting date/time (note says: {r.get('notes')!r}). Add it to the calendar by hand.")
    if "deals" in tables:
        d = [dict(x) for x in db.execute("select * from deals")]; rep["source_rows"]["deals"] = len(d)
        for x in d:
            deals.append({"legacy_key": f"{sha[:8]}:{x['id']}", "client": x["client"], "upfront": x["upfront"] or 0, "monthly": x["monthly"] or 0,
                          "months": x["months"] or 0, "closed_at": day(x["closed_at"]), "first_bill": day(x["first_bill"]),
                          "notes": x["notes"] or "", "source": "legacy"})
    if "events" in tables:
        e = [dict(x) for x in db.execute("select * from events")]; rep["source_rows"]["events"] = len(e)
        ids = {l["id"] for l in leads}
        for x in e:
            if not day(x["day"]): bad.append({"table": "events", "id": x["id"], "why": "bad date"}); continue
            events.append({"legacy_key": f"{sha[:8]}:{x['id']}", "title": x["title"], "day": x["day"], "start_time": x["start_time"] or "",
                           "color": x["color"] or "", "icon": x["icon"] or "", "repeat_kind": x["repeat_kind"] or "none",
                           "until": day(x["until"]), "notes": x["notes"] or "", "lead_id": x["lead_id"] if x["lead_id"] in ids else None, "source": "legacy"})
    rep["customers_imported"] = len(leads); rep["calls_derived_from_status"] = len(calls)
    rep["calendar_events_imported"] = len(events); rep["deals_imported"] = len(deals)
    rep["notes_imported"] = sum(1 for l in leads if l["notes"].strip())  # per-lead notes (the old app had no separate notes feature)
    rep["activities_imported"] = 0   # the old app kept no activity history; none is invented
    rep["duplicates_identified"] = len(dups); rep["records_not_migrated"] = len(bad); rep["not_migrated_detail"] = bad
    rep["legacy_tables_absent"] = [t for t in ("employees", "calls", "call_log", "notes", "activity") if t not in tables]
    return rep, leads, calls, deals, events, dups


def post(url, key, table, rows, on_conflict=None, chunk=200):
    import requests
    h = {"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json",
         "Prefer": "resolution=ignore-duplicates,return=minimal" if on_conflict else "return=minimal"}
    q = f"?on_conflict={on_conflict}" if on_conflict else ""
    for i in range(0, len(rows), chunk):
        r = requests.post(f"{url}/rest/v1/{table}{q}", headers=h, data=json.dumps(rows[i:i + chunk]), timeout=60)
        if r.status_code >= 300: raise SystemExit(f"{table}: HTTP {r.status_code} {r.text[:300]}")


def count(url, key, table, where=""):
    import requests
    r = requests.get(f"{url}/rest/v1/{table}?select=id{where}", headers={"apikey": key, "Authorization": "Bearer " + key, "Prefer": "count=exact", "Range": "0-0"}, timeout=60)
    return int(r.headers["Content-Range"].split("/")[1])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("db"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--owner", help="username of the employee who used the old PC; omit to leave UNASSIGNED")
    ap.add_argument("--tz", default="America/Toronto"); ap.add_argument("--report", default="migration_report.json")
    a = ap.parse_args()
    try: ZoneInfo(a.tz)
    except Exception: sys.exit("The time zone database is missing. Run:  python -m pip install tzdata   and try again.")
    sha = hashlib.sha256(open(a.db, "rb").read()).hexdigest()
    rep, leads, calls, deals, events, dups = build(a.db, ZoneInfo(a.tz), a.owner, sha)
    rep["source_sha256"] = sha; rep["applied"] = False
    if a.apply:
        url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key: sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY first.")
        import requests
        owner_id = None
        if a.owner:
            r = requests.get(f"{url}/rest/v1/profiles?username=eq.{a.owner.lower()}&select=id", headers={"apikey": key, "Authorization": "Bearer " + key}, timeout=30).json()
            if not r: sys.exit(f"No employee '{a.owner}'. Run seed_users.py first.")
            owner_id = r[0]["id"]
        os.makedirs("legacy_backups", exist_ok=True); stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bk = os.path.join("legacy_backups", f"{stamp}-{os.path.basename(a.db)}"); shutil.copy2(a.db, bk)
        if hashlib.sha256(open(bk, "rb").read()).hexdigest() != sha: sys.exit("Backup copy does not match the source; aborting.")
        rep["source_backup"] = bk
        if count(url, key, "leads") > 0:
            here = os.path.dirname(os.path.abspath(__file__)); rb = os.path.join("legacy_backups", f"{stamp}-shared-db-before-import")
            if subprocess.run([sys.executable, os.path.join(here, "backup.py"), rb]).returncode: sys.exit("Backup of the shared database failed; aborting.")
            rep["shared_db_backup"] = rb
        have = requests.get(f"{url}/rest/v1/leads?select=id,phone_key&limit=100000", headers={"apikey": key, "Authorization": "Bearer " + key}, timeout=60).json()
        have_ids = {x["id"] for x in have}; have_keys = {x["phone_key"] for x in have if x["phone_key"]}
        kept = []
        for l in leads:
            k = digits10(l["phone"])
            if l["id"] in have_ids or (k and k in have_keys):
                dups.append({"kept_lead_id": l["id"] if l["id"] in have_ids else None, "reason": "already in shared database (same id or phone)", "original": l["raw"]})
            else: kept.append(l)
        gone = {l["id"] for l in leads} - {l["id"] for l in kept}
        leads = kept; calls = [c for c in calls if c["lead_id"] not in gone]; events = [e for e in events if e["lead_id"] not in gone]
        rep["customers_imported"], rep["calls_derived_from_status"], rep["duplicates_identified"] = len(leads), len(calls), len(dups)
        for l in leads: l["called_by"] = owner_id if l["called_at"] else None
        for c in calls: c["employee_id"] = owner_id
        for d in deals: d["owner_id"] = owner_id
        before = {t: count(url, key, t) for t in ("leads", "call_log", "deals", "events")}
        # Re-running is harmless: duplicates by id/phone/legacy_id are ignored, never overwritten.
        post(url, key, "leads", leads, "id")
        # derived calls get a deterministic op id so a re-run cannot double them
        for c in calls: c["client_op_id"] = hashlib.md5(("legacy-call:" + c["lead_id"]).encode()).hexdigest()
        post(url, key, "call_log", calls, "client_op_id")
        post(url, key, "deals", deals, "legacy_key"); post(url, key, "events", events, "legacy_key")
        batch = requests.post(f"{url}/rest/v1/import_batches", headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json", "Prefer": "return=representation"},
                              data=json.dumps({"source_file": os.path.basename(a.db), "source_sha256": sha, "report": rep}), timeout=30).json()[0]["id"]
        post(url, key, "legacy_duplicates", [{"batch_id": batch, "kept_lead_id": d["kept_lead_id"], "reason": d["reason"], "original": d["original"]} for d in dups])
        after = {t: count(url, key, t) for t in before}
        rep["verification"] = {t: {"before": before[t], "after": after[t], "added": after[t] - before[t]} for t in before}
        rep["verified_in_database"] = {"legacy_leads": count(url, key, "leads", "&source=eq.legacy")}
        rep["applied"] = True
    json.dump(rep, open(a.report, "w"), indent=2, default=str)
    show = {k: v for k, v in rep.items() if k not in ("not_migrated_detail",)}
    print(json.dumps(show, indent=2, default=str)); print("\nReport written to", a.report, "(APPLIED)" if rep["applied"] else "(dry run: nothing was sent)")


if __name__ == "__main__": main()
