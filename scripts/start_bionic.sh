#!/bin/sh
set -eu
LMS='/Applications/Bionic.app/Contents/Resources/app/.webpack-bionic/lms'
"$LMS" server start --port 1234 --bind 127.0.0.1
# Explicit model selection; never unload someone else's model automatically.
case "${1:-nemotron}" in
  nemotron) "$LMS" load nemotron --identifier omnijev-nemotron --context-length 8192 --gpu max -y ;;
  qwen) "$LMS" load Qwen3.8 --identifier omnijev-qwen --context-length 8192 -y ;;
  *) echo 'Usage: sh scripts/start_bionic.sh [nemotron|qwen]' >&2; exit 1 ;;
esac
