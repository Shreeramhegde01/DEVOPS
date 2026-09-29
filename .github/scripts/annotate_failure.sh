#!/usr/bin/env bash
# Turns the tail of the CI log (and optional extra diagnostics) into GitHub annotations, so the reason for a
# failure is visible on the workflow run's summary page without opening the raw logs.
#
# Usage (in a step with `if: failure()`):  bash .github/scripts/annotate_failure.sh ["diagnostic command"]
annotate() {   # $1 = title, stdin = text
  python3 -c '
import sys
lines = [line.split("\r")[-1] for line in sys.stdin.read().splitlines()]   # drop progress-bar redraws
text = "\n".join(lines)[-3500:]
text = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
print(f"::error title={sys.argv[1]}::{text}")' "$1"
}

tail -n 60 "${CI_LOG:-/tmp/ci.log}" 2>/dev/null | annotate "Failure log (last lines)"
if [ -n "${1:-}" ]; then
  bash -c "$1" 2>&1 | tail -n 60 | annotate "Diagnostics"
fi
