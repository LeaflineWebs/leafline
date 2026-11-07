#!/usr/bin/env bash
# Builds Leafline-Lead-Finder-<version>-<arch>.dmg  (run this ON a Mac; needs Python 3.10+ and Node.js 18+)
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
rm -rf backend-dist
python3 -m PyInstaller --noconfirm --name leafline_backend --distpath backend-dist --workpath build/pyi --specpath build/pyi --collect-all playwright --collect-data tzdata backend/leafline_backend.py
npm install
CSC_IDENTITY_AUTO_DISCOVERY=false npm run dist:mac
echo; echo 'Done. Your DMG is in the "dist" folder.'
