#!/usr/bin/env bash
# Publishes a file (or stdin) as a GitHub "notice" annotation - used to surface lab results on the run summary.
# Usage: notice.sh "Title" [file]
title="$1"
python3 -c '
import sys
text = (open(sys.argv[2]).read() if len(sys.argv) > 2 else sys.stdin.read())[-7000:]
text = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
print(f"::notice title={sys.argv[1]}::{text}")' "$title" "${@:2}"
