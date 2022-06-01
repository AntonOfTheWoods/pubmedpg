#! /usr/bin/env sh
set -e

PRE_START_PATH=${PRE_START_PATH:-/app/scripts/prestart.sh}
. "$PRE_START_PATH"

python pub_med_parser.py
