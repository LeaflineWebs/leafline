"""Shared setup for Messages tests: the in-memory fake Supabase, with messaging forwarded to tests/pg/server.mjs
(a real Postgres running the real migrations). Needs Node and `npm install` in tests/pg once."""
import os, sys, subprocess, atexit, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
PG = os.path.join(HERE, "pg")


def available():
    return bool(shutil.which("node")) and os.path.isdir(os.path.join(PG, "node_modules", "@electric-sql", "pglite"))


def start_pg_server():
    """Starts the real-Postgres test server; returns its base URL."""
    p = subprocess.Popen(["node", os.path.join(PG, "server.mjs")], cwd=PG, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    atexit.register(lambda: p.kill())
    while True:
        line = p.stdout.readline()
        if not line:
            raise SystemExit("The Postgres test server did not start.")
        if line.startswith("READY "):
            port = int(line.split()[1])
            break
    import threading
    threading.Thread(target=lambda: [None for _ in p.stdout], daemon=True).start()   # keep draining its output
    return f"http://127.0.0.1:{port}"
