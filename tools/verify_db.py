#!/usr/bin/env python3
"""Check the live Leafline database from the admin PC. Read-only except one probe that is expected to be REFUSED.

  python verify_db.py                       # tables, row level security, accounts and roles
  python verify_db.py --as gio NewPassword  # also test what a normal employee can and cannot do

Needs tools/.env (SUPABASE_URL, SUPABASE_SECRET_KEY) and the publishable key (built into the app, or SUPABASE_PUBLISHABLE_KEY).
"""
import os, sys, json, requests
import _env  # noqa: F401

URL = os.environ["SUPABASE_URL"].rstrip("/"); SECRET = os.environ["SUPABASE_SERVICE_KEY"]
PUB = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "sb_publishable_6ssgQB4Z9D3lYtBtL3m8uA_B4w0fFiQ"
DOM = os.environ.get("LEAFLINE_EMAIL_DOMAIN") or "leaflineweb.com"
TABLES = ["profiles", "leads", "call_log", "deals", "events", "notes", "activity", "settings", "audit_log", "import_batches", "legacy_duplicates"]
ROLES = {"james": "admin", "omar": "admin", "akbar": "admin", "gio": "employee", "jaylen": "employee", "tim": "employee"}
bad = 0


def say(ok, msg, hard=True):
    global bad
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok and hard: bad += 1


def get(table, key, token=None, params="select=*&limit=5", method="GET", body=None):
    h = {"apikey": key, "Authorization": "Bearer " + (token or key), "Content-Type": "application/json", "Prefer": "count=exact"}
    return requests.request(method, f"{URL}/rest/v1/{table}?{params}", headers=h, data=json.dumps(body) if body is not None else None, timeout=30)


def count(r):
    try: return int(r.headers.get("Content-Range", "*/0").split("/")[1])
    except ValueError: return 0


print("1. Tables exist (checked with the secret key)")
have = {}
for t in TABLES:
    r = get(t, SECRET, params="select=*&limit=1")
    have[t] = count(r) if r.status_code in (200, 206) else None
    say(r.status_code in (200, 206), f"{t}" + (f" ({have[t]} rows)" if r.status_code in (200, 206) else f" MISSING (HTTP {r.status_code}: {r.text[:120]})"))

print("2. Row level security (anonymous visitors, using only the public key, must see nothing)")
for t in TABLES:
    if have.get(t) is None: continue
    r = get(t, PUB, params="select=*&limit=5")
    seen = len(r.json()) if r.status_code in (200, 206) and isinstance(r.json(), list) else 0
    say(r.status_code in (401, 403) or seen == 0, f"{t}: anonymous sees {seen} rows" + ("  <-- RLS IS NOT PROTECTING THIS TABLE" if seen else ""))
r = get("leads", PUB, method="POST", body={"id": "rls-probe", "name": "probe"}, params="")
say(r.status_code in (401, 403), f"anonymous INSERT into leads refused (HTTP {r.status_code})")
if requests.get(f"{URL}/rest/v1/leads?id=eq.rls-probe&select=id", headers={"apikey": SECRET, "Authorization": "Bearer " + SECRET}, timeout=30).json():
    requests.delete(f"{URL}/rest/v1/leads?id=eq.rls-probe", headers={"apikey": SECRET, "Authorization": "Bearer " + SECRET}, timeout=30); say(False, "probe row was created and has been removed")
if have.get("settings"): 
    r = get("settings", PUB); say(not (r.status_code in (200, 206) and r.json()), "seeded daily_targets row hidden from anonymous (proves RLS is on)")

print("3. Accounts and roles")
prof = {p["username"]: p for p in get("profiles", SECRET, params="select=*").json()} if have.get("profiles") is not None else {}
for u, role in ROLES.items():
    p = prof.get(u)
    say(p is not None and p["role"] == role and p["active"], f"{u}: " + ("missing (run seed_users.py seed)" if not p else f"role={p['role']} active={p['active']} must_change_password={p['must_change_password']}"))
extra = sorted(set(prof) - set(ROLES))
if extra: print("  note  other accounts:", ", ".join(extra))
r = requests.post(f"{URL}/rest/v1/rpc/daily_stats", headers={"apikey": SECRET, "Authorization": "Bearer " + SECRET, "Content-Type": "application/json"}, json={"p_from": "2026-01-01", "p_to": "2026-12-31"}, timeout=30)
say(r.status_code in (200, 206), f"daily_stats() works (HTTP {r.status_code})")

if "--as" in sys.argv:
    u, pw = sys.argv[sys.argv.index("--as") + 1:][:2]
    print(f"4. What '{u}' is allowed to do")
    a = requests.post(f"{URL}/auth/v1/token?grant_type=password", headers={"apikey": PUB}, json={"email": f"{u}@{DOM}", "password": pw}, timeout=30)
    say(a.status_code in (200, 206), "sign-in works")
    if a.status_code in (200, 206):
        tok = a.json()["access_token"]; admin = ROLES.get(u) == "admin"
        for t in ("leads", "profiles", "settings", "activity", "call_log"): 
            r = get(t, PUB, tok); say(r.status_code in (200, 206), f"can read {t}")
        r = get("audit_log", PUB, tok); n = len(r.json()) if r.status_code in (200, 206) else 0
        say((n > 0 or have["audit_log"] == 0) if admin else n == 0, f"audit_log: sees {n} rows ({'admin may read' if admin else 'employees must see none'})")
        sv = lambda: get("settings", SECRET, params="key=eq.daily_targets&select=value").json()
        before = sv()
        r = get("settings", PUB, tok, params="key=eq.daily_targets", method="PATCH", body={"value": {"calls": 1, "connections": 1, "meetings": 1, "sales": 1}})
        after = sv()
        changed = before != after
        say(admin or not changed, f"changing daily targets {'allowed (admin)' if admin else 'refused'}: HTTP {r.status_code}, value {'CHANGED' if changed else 'unchanged'}")
        if changed:
            requests.patch(f"{URL}/rest/v1/settings?key=eq.daily_targets", headers={"apikey": SECRET, "Authorization": "Bearer " + SECRET, "Content-Type": "application/json"}, json={"value": before[0]["value"]}, timeout=30)
            print("  note  daily targets were restored to their previous value")
        r = get("profiles", PUB, tok, params=f"username=eq.{u}", method="PATCH", body={"role": "admin"})
        me = get("profiles", SECRET, params=f"username=eq.{u}&select=role").json()
        promoted = bool(me) and me[0]["role"] == "admin" and ROLES.get(u) != "admin"
        say(not promoted, "cannot promote itself to admin")
        if promoted:
            requests.patch(f"{URL}/rest/v1/profiles?username=eq.{u}", headers={"apikey": SECRET, "Authorization": "Bearer " + SECRET, "Content-Type": "application/json"}, json={"role": ROLES.get(u, "employee")}, timeout=30)
            print("  note  the test promoted this account; its role has been set back automatically")
print()
print("NOT checked here (cannot be read through the API): the Realtime publication. Dashboard > Database > Publications > supabase_realtime should list leads, call_log, deals, events, notes, activity, profiles, settings. The app does not depend on it yet.")
print("ALL CHECKS PASSED" if not bad else f"{bad} CHECK(S) FAILED: send this output to Claude")
sys.exit(1 if bad else 0)
