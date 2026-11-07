"""Loads tools/.env (admin secrets) into os.environ. Never imported by the app itself."""
import os
def load():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"'))
    if os.environ.get("SUPABASE_SECRET_KEY") and not os.environ.get("SUPABASE_SERVICE_KEY"):
        os.environ["SUPABASE_SERVICE_KEY"] = os.environ["SUPABASE_SECRET_KEY"]
load()
