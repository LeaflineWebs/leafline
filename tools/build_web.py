#!/usr/bin/env python3
"""Builds the website (the docs/ folder) from the same interface the desktop app uses.
Run:  python tools/build_web.py        (PUSH_UPDATE.bat does this for you)
Only PUBLIC values go into the website: the Supabase address and the publishable key. Never a secret key."""
import hashlib, json, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
OUT = os.path.join(ROOT, "docs"); SRC = os.path.join(ROOT, "web_src")


def version():
    with open(os.path.join(ROOT, "package.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


def build(out=OUT):
    import leafline_backend as b, leafline_sync as ls
    key, url = ls.PUBLISHABLE_KEY, ls.SUPABASE_URL
    if "secret" in key.lower() or not key.startswith("sb_publishable_"):
        raise SystemExit("Refusing to build: the key in the app is not a publishable key.")
    v = version()
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        p = os.path.join(out, f)
        if os.path.isfile(p) and f != "CNAME": os.remove(p)
    ui = b.UI_HTML
    ui = re.sub(r',url\("__FONT_(?:REG|BOLD)__"\) format\("truetype"\)', "", ui)        # the optional bundled font files are not part of the website
    assert "__FONT_" not in ui
    head = ('<meta name="theme-color" content="#0A120E">\n<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n<meta name="apple-mobile-web-app-title" content="Leafline">\n'
            '<link rel="manifest" href="manifest.webmanifest">\n<link rel="apple-touch-icon" href="apple-touch-icon.png">\n<link rel="icon" href="icon-192.png">\n'
            '<script src="config.js?v=%s"></script>\n<script src="engine.js?v=%s"></script>\n' % (v, v))
    assert "<head>" in ui
    ui = ui.replace("<head>", "<head>\n" + head, 1).replace("<title>Leafline Web Services - Lead Finder</title>", "<title>Leafline</title>", 1)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(ui)
    shutil.copy(os.path.join(SRC, "engine.js"), os.path.join(out, "engine.js"))
    h = hashlib.sha256()
    for f in ("index.html", "engine.js", "sw.js", "manifest.webmanifest"):
        h.update(open(os.path.join(out if f == "index.html" or f == "engine.js" else SRC, f), "rb").read())
    build = v + "-" + h.hexdigest()[:8]
    open(os.path.join(out, "config.js"), "w", encoding="utf-8").write(
        "window.LF_CONFIG=%s;\n" % json.dumps({"url": url, "key": key, "version": v, "build": build}))
    files = ["index.html", "engine.js", "config.js"]
    for f in ("manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png", "icon-maskable-512.png"):
        shutil.copy(os.path.join(SRC, f), os.path.join(out, f))
    sw = open(os.path.join(SRC, "sw.js"), encoding="utf-8").read().replace("__VERSION__", build)
    open(os.path.join(out, "sw.js"), "w", encoding="utf-8").write(sw)
    open(os.path.join(out, ".nojekyll"), "w").write("")
    open(os.path.join(out, "version.json"), "w", encoding="utf-8").write(json.dumps({"version": v, "build": build}) + "\n")
    # last safety net: nothing secret may be inside the website
    for f in os.listdir(out):
        if f.endswith((".html", ".js", ".json", ".webmanifest")) and re.search(r"sb_secre[t]_|service_rol[e]", open(os.path.join(out, f), encoding="utf-8", errors="ignore").read()):
            raise SystemExit("Refusing to build: a secret key appears in " + f)
    return v


if __name__ == "__main__":
    print("Website built (version %s) in %s" % (build(), OUT))
