#!/bin/sh
cd "$(dirname "$0")"
Xephyr -ac -br -noreset -screen 1024x768 :1 &
export DISPLAY=:1.0
sleep 1
fluxbox &
./run.py --test --devel "$@"
