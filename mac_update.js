"use strict";
// The Mac app can't use the standard updater without a paid Apple signing certificate, so it updates itself:
// updater.js downloads and checks the new version's .zip, then runs this script and quits. The script waits for the
// app to close, unpacks the new app, swaps it in place of the old one (putting the old one back if anything fails)
// and opens it again. Arguments: <path of the .app> <downloaded .zip> <pid of the running app> <work folder>.
// Set LEAFLINE_NO_OPEN=1 to skip reopening (used by the online test of this script).
module.exports = `#!/bin/bash
APP="$1"; ZIP="$2"; PID="$3"; WORK="$4"
LOG="$WORK/install.log"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
reopen() { [ -n "$LEAFLINE_NO_OPEN" ] || /usr/bin/open "$APP"; }
case "$APP" in *.app) ;; *) say "not an app bundle: $APP"; exit 1;; esac
[ -f "$ZIP" ] || { say "no download at $ZIP"; reopen; exit 1; }
for i in $(seq 1 240); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
NEWDIR="$WORK/unpacked"
/bin/rm -rf "$NEWDIR"; /bin/mkdir -p "$NEWDIR"
if ! /usr/bin/ditto -x -k "$ZIP" "$NEWDIR"; then say "could not unpack $ZIP"; reopen; exit 1; fi
NEW="$(/usr/bin/find "$NEWDIR" -maxdepth 1 -name '*.app' -print -quit)"
[ -n "$NEW" ] || { say "no app inside $ZIP"; reopen; exit 1; }
/bin/rm -rf "$APP.old"
if ! /bin/mv "$APP" "$APP.old"; then say "could not move the old app aside"; reopen; exit 1; fi
if /usr/bin/ditto "$NEW" "$APP"; then
  /bin/rm -rf "$APP.old"; say "updated $APP"
else
  say "copy failed, putting the old app back"; /bin/rm -rf "$APP"; /bin/mv "$APP.old" "$APP"
fi
/usr/bin/xattr -dr com.apple.quarantine "$APP" 2>/dev/null
/bin/rm -rf "$NEWDIR" "$ZIP"
reopen
`;
