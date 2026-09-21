#!/bin/sh
set -eu
cd "$(dirname "$0")"
LMS='/Applications/Bionic.app/Contents/Resources/app/.webpack-bionic/lms'
if [ "$#" -gt 0 ]; then
  echo 'Custom server flags: use your already running model backend.'
elif [ -x "$LMS" ]; then
  "$LMS" server start --port 1234 --bind 127.0.0.1
  if ! python3 -c 'import json,urllib.request; rows=json.load(urllib.request.urlopen("http://127.0.0.1:1234/api/v0/models",timeout=5))["data"]; raise SystemExit(0 if any(r["id"]=="omnijev-nemotron" and r.get("state")=="loaded" for r in rows) else 1)'; then
    "$LMS" load nemotron --identifier omnijev-nemotron --context-length 8192 --gpu max -y
  fi
else
  echo 'Bionic CLI not found; expecting an existing compatible server at 127.0.0.1:1234.'
fi
exec python3 -m omnijev.server "$@"
