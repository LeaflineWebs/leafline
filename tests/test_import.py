import os, sys, subprocess, json, shutil, tempfile, sqlite3, hashlib
os.environ["NO_PROXY"] = "127.0.0.1"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fake_supabase import Fake
F = Fake()
for n in ("gio", "james", "akbar", "omar", "jaylen", "tim"): F.add_user(n, n.title() + "123", "admin" if n in ("james", "omar", "akbar") else "employee")
env = dict(os.environ, SUPABASE_URL=F.url, SUPABASE_SECRET_KEY="sb_secret_test")
work = tempfile.mkdtemp(); U = "/mnt/user-data/uploads/"
def run(db, owner, tag):
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "tools", "import_legacy.py"), db, "--apply", "--owner", owner, "--report", f"{work}/{tag}.json"], env=env, capture_output=True, text=True, cwd=work, timeout=120)
    if r.returncode: print(r.stdout[-600:], r.stderr[-800:])
    return json.load(open(f"{work}/{tag}.json")) if r.returncode == 0 else None
before = {f: hashlib.sha256(open(U + f, "rb").read()).hexdigest() for f in ("leads_v2.db", "leads_v2_1.db")}
ok = fail = 0
def check(l, c):
    global ok, fail
    if c: ok += 1; print("  PASS", l)
    else: fail += 1; print("  FAIL", l)
a = run(U + "leads_v2_1.db", "akbar", "akbar"); 
print("AKBAR:", {k: a[k] for k in ("source_rows", "customers_imported", "calls_derived_from_status", "deals_imported", "calendar_events_imported", "notes_imported", "duplicates_identified", "records_not_migrated")})
akbar_id = next(p["id"] for p in F.t["profiles"] if p["username"] == "akbar")
check("all Akbar's non-duplicate leads imported", a["customers_imported"] + a["duplicates_identified"] == a["source_rows"]["leads"])
check("his worked leads are attributed to akbar", F.t["call_log"] and all(c["employee_id"] == akbar_id for c in F.t["call_log"]) and all(l["called_by"] == akbar_id for l in F.t["leads"] if l["called_at"]))
check("derived calls flagged legacy_status (excluded from live stats)", all(c["source"] == "legacy_status" for c in F.t["call_log"]))
n_a = len(F.t["leads"]); w_a = sum(1 for l in F.t["leads"] if l["status"] != "none")
j = run(U + "leads_v2.db", "james", "james")
print("JAMES:", {k: j[k] for k in ("source_rows", "customers_imported", "calls_derived_from_status", "deals_imported", "calendar_events_imported", "notes_imported", "duplicates_identified", "records_not_migrated")})
james_id = next(p["id"] for p in F.t["profiles"] if p["username"] == "james")
check("James's file imported on top without overwriting Akbar's", len(F.t["leads"]) >= n_a and sum(1 for l in F.t["leads"] if l["status"] != "none" and l["called_by"] == akbar_id) == w_a)
check("James's deals attributed to james", len(F.t["deals"]) == 4 and all(d["owner_id"] == james_id for d in F.t["deals"]))
check("overlapping leads were archived, not dropped", j["duplicates_identified"] > 7 and len(F.t["legacy_duplicates"]) >= j["duplicates_identified"] + a["duplicates_identified"])
check("pre-import backups were made", "source_backup" in j and "shared_db_backup" in j and any("leads.json" in fs for _, _, fs in os.walk(os.path.join(work, j["shared_db_backup"]))))
total = len(F.t["leads"]); deals = len(F.t["deals"]); calls = len(F.t["call_log"])
j2 = run(U + "leads_v2.db", "james", "james2"); a2 = run(U + "leads_v2_1.db", "akbar", "akbar2")
check("re-running both imports adds nothing", (len(F.t["leads"]), len(F.t["deals"]), len(F.t["call_log"])) == (total, deals, calls))
check("no duplicate phone numbers in shared db", len({l["phone_key"] for l in F.t["leads"] if l["phone_key"]}) == sum(1 for l in F.t["leads"] if l["phone_key"]))
check("original files untouched", before == {f: hashlib.sha256(open(U + f, "rb").read()).hexdigest() for f in before})
print(f"\nSHARED DB: {len(F.t['leads'])} leads, {len(F.t['call_log'])} derived calls, {len(F.t['deals'])} deals; {ok} passed, {fail} failed")
json.dump({"akbar": a, "james": j}, open("/tmp/import_reports.json", "w"), indent=1, default=str); sys.exit(1 if fail else 0)
