#!/usr/bin/env bash
# Confirm the package works on this machine, before trusting anything it produces.
#
#   ./verify_install.sh /path/to/index/files
set -u

DATA="${1:-${ISF_DATA_DIR:-}}"
if [ -z "$DATA" ]; then
  echo "usage: ./verify_install.sh /path/to/index/files"
  echo "   or: export ISF_DATA_DIR=/path/to/index/files && ./verify_install.sh"
  exit 1
fi
export ISF_DATA_DIR="$DATA"

step() { printf '\n=== %s ===\n' "$1"; }
fail() { echo "FAILED: $1"; exit 1; }

step "Python version"
python3 --version || fail "Python 3.10+ is required"

step "Dependencies"
python3 -c "import openpyxl; print('openpyxl', openpyxl.__version__)" \
  || fail "pip install -r requirements.txt"
python3 -c "import pycountry; print('pycountry ok')" \
  || echo "  pycountry missing — country codes will show as AGO, not Angola"

step "Where it is pointed"
python3 -m isf.paths || fail "ISF_DATA_DIR does not point at a usable folder"

step "Do the published scores still reproduce?"
python3 -m isf.engine_core.selfcheck || fail "an index no longer reproduces its published score"

step "Build the workbook"
python3 -m isf.build_export || fail "export"

step "Build the deck"
python3 -m isf.build_deck || fail "deck"

printf '\n=== Everything works. Output is in %s ===\n' "${ISF_OUTPUT_DIR:-./output}"
