#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.9+ needed'; exit 2; }
python3 -c 'import sys; assert sys.version_info >= (3,9)'
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m metric_atlas.cli build --input data/observations.json --output run
printf 'Dashboard: %s/run/index.html\n' "$(pwd)"
