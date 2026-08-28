#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/validate_all.py"
for p in 02-verified-browser-ops-agent 03-governed-mysql-data-agent 04-java-migration-agent 05-evidence-deep-research-agent; do
  echo "== $p =="
  (cd "$ROOT/$p" && python3 -m unittest discover -s tests -v)
done
(cd "$ROOT/03-governed-mysql-data-agent" && python3 scripts/init_demo.py >/dev/null && python3 -m src.cli revenue)
echo "Quickcheck PASS / 快速检查通过"
