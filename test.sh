#!/bin/sh
cd "$(dirname "$0")"
Xephyr -ac -br -noreset -screen 1024x768 :1 &
export DISPLAY=:1.0
sleep 1
fluxbox &
FB_PID="$!"
./run.py --test --devel "$@"
kill -9 "$FB_PID"
