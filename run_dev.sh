#!/usr/bin/env bash
# Runs the app from source (no installer). Needs Python 3.10+ and Node.js 18+.
set -e
cd "$(dirname "$0")"
grep -q leafline-lead-finder package.json || { echo "This folder's package.json is not the Leafline one."; exit 1; }
python3 -m pip install requests playwright tzdata
[ -d node_modules ] || npm install
npm start
