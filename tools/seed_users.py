#!/usr/bin/env python3
"""Create / manage Leafline employee accounts (admin PC only; uses the SECRET service key).

  python seed_users.py seed                 # Gio, James, Akbar, Omar, Jaylen, Tim (James, Omar, Akbar are admins), then Kyle and Mubaraq
  python seed_users.py starters             # only the newer starters: Kyle and Mubaraq (regular employees)
  python seed_users.py add Sarah            # new employee, random temporary password printed once
  python seed_users.py reset James          # new temporary password, forces change at next login
  python seed_users.py reactivate Tim       # lets a deactivated person sign in again
  python seed_users.py deactivate Tim       # blocks sign-in and all data access (records are kept)

Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, optional LEAFLINE_EMAIL_DOMAIN (default leaflineweb.com;
no email is ever sent, the address is only a login handle).
Passwords are hashed by Supabase Auth (bcrypt). Nothing here is stored in plaintext anywhere.
DELETE or keep this file off the employees' PCs: it contains the six temporary starter passwords.
"""
import os, secrets, sys, requests
import _env  # noqa: F401

URL = os.environ.get("SUPABASE_URL", "").rstrip("/"); KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DOM = os.environ.get("LEAFLINE_EMAIL_DOMAIN", "leaflineweb.com")
H = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
ADMINS = {"james", "omar", "akbar"}
STARTERS = {"Gio": "Gio123", "James": "James123", "Akbar": "Akbar123", "Omar": "Omar123", "Jaylen": "Jaylen123", "Tim": "Tim123"}
# Starters added later (11.15). Regular employees, never admins. No password is written anywhere: each gets a random
# temporary one, printed once, and must choose their own at first sign-in (exactly like "add").
NEW_STARTERS = ["Kyle", "Mubaraq"]


def email(u): return f"{u.lower()}@{DOM}"
def temp_pw(): return secrets.token_urlsafe(12)


def user_id(u):
    r = requests.get(f"{URL}/rest/v1/profiles?username=eq.{u.lower()}&select=id", headers=H, timeout=30).json()
    return r[0]["id"] if r else None


def create(name, pw, role="employee"):
    u = name.lower()
    if user_id(u): print(f"  {name}: already exists, skipped"); return False
    r = requests.post(f"{URL}/auth/v1/admin/users", headers=H, timeout=30,
                      json={"email": email(u), "password": pw, "email_confirm": True, "user_metadata": {"username": u}})
    if r.status_code >= 300: sys.exit(f"  {name}: {r.status_code} {r.text[:300]}")
    p = requests.post(f"{URL}/rest/v1/profiles", headers=H, timeout=30,
                      json={"id": r.json()["id"], "username": u, "display_name": name, "role": role, "must_change_password": True})
    if p.status_code >= 300: sys.exit(f"  {name}: profile failed {p.status_code} {p.text[:300]}")
    print(f"  {name}: created ({role}), must change password at first login"); return True


def main():
    if not URL or not KEY: sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY first.")
    a = sys.argv[1:]; cmd = a[0] if a else ""
    if cmd in ("seed", "starters"):
        if cmd == "seed":
            for n, pw in STARTERS.items(): create(n, pw, "admin" if n.lower() in ADMINS else "employee")
        for n in NEW_STARTERS:
            pw = temp_pw()
            if create(n, pw, "employee"): print(f"  {n}: temporary password {pw}  (login name: {n})")
    elif cmd == "add" and len(a) > 1:
        pw = temp_pw()
        if create(a[1], pw): print(f"  temporary password: {pw}")
    elif cmd == "reset" and len(a) > 1:
        uid = user_id(a[1]) or sys.exit("No such employee."); pw = temp_pw()
        requests.put(f"{URL}/auth/v1/admin/users/{uid}", headers=H, json={"password": pw}, timeout=30).raise_for_status()
        requests.patch(f"{URL}/rest/v1/profiles?id=eq.{uid}", headers=H, json={"must_change_password": True}, timeout=30).raise_for_status()
        print(f"  {a[1]}: temporary password {pw} (must change at next login)")
    elif cmd == "reactivate" and len(a) > 1:
        uid = user_id(a[1]) or sys.exit("No such employee.")
        requests.patch(f"{URL}/rest/v1/profiles?id=eq.{uid}", headers=H, json={"active": True}, timeout=30).raise_for_status()
        requests.put(f"{URL}/auth/v1/admin/users/{uid}", headers=H, json={"ban_duration": "none"}, timeout=30).raise_for_status()
        print(f"  {a[1]}: active again")
    elif cmd == "deactivate" and len(a) > 1:
        uid = user_id(a[1]) or sys.exit("No such employee.")
        requests.patch(f"{URL}/rest/v1/profiles?id=eq.{uid}", headers=H, json={"active": False}, timeout=30).raise_for_status()
        requests.put(f"{URL}/auth/v1/admin/users/{uid}", headers=H, json={"ban_duration": "876000h"}, timeout=30).raise_for_status()
        print(f"  {a[1]}: deactivated (history kept)")
    else: print(__doc__)


if __name__ == "__main__": main()
