#!/usr/bin/env python3
"""Export every shared table to JSON files (admin / scheduled job; uses the SECRET service key).
Personal notes are deliberately NOT exported so a backup can never expose private writing.
  python backup.py [folder]"""
import json, os, sys, datetime, requests
import _env  # noqa: F401
URL = os.environ["SUPABASE_URL"].rstrip("/"); KEY = os.environ["SUPABASE_SERVICE_KEY"]
H = {"apikey": KEY, "Authorization": "Bearer " + KEY}
TABLES = {"profiles": "", "leads": "", "call_log": "", "deals": "", "events": "", "notes": "&scope=eq.shared",
          "activity": "", "settings": "", "audit_log": "", "import_batches": "", "legacy_duplicates": ""}
out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else ".", "leafline-backup-" + datetime.date.today().isoformat())
os.makedirs(out, exist_ok=True); total = {}
for t, f in TABLES.items():
    rows, i = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{t}?select=*{f}", headers={**H, "Range": f"{i}-{i + 999}"}, timeout=120)
        r.raise_for_status(); b = r.json(); rows += b
        if len(b) < 1000: break
        i += 1000
    json.dump(rows, open(os.path.join(out, t + ".json"), "w"), indent=1); total[t] = len(rows)
print(out, total)
