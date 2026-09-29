#!/usr/bin/env bash
# Resilience test: crash the AI service container and verify Docker restarts it and the API recovers.
#
# The crash is simulated from *inside* the container (SIGINT to PID 1 makes the Flask/Python process exit).
# `docker kill` / `docker stop` would not work for this test: Docker treats those as a deliberate stop and
# does not apply the restart policy.
#
# Usage: ./resilience_test.sh            (env: SERVICE_URL=http://localhost:5001  PYTHON=python3)
set -euo pipefail
cd "$(dirname "$0")/.."

CONTAINER=ai-artistic-style
SERVICE_URL="${SERVICE_URL:-http://localhost:5001}"
PYTHON="${PYTHON:-python3}"

restarts() { docker inspect -f '{{.RestartCount}}' "$CONTAINER"; }

before=$(restarts)
echo "== Restart count before: $before   (restart policy: $(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CONTAINER"))"

echo "== Simulating a crash of the AI service (process inside $CONTAINER exits)"
crashed_at=$(date +%s)
docker exec "$CONTAINER" sh -c 'kill -INT 1' || true

echo "== Waiting for Docker to restart the container ..."
for _ in $(seq 1 60); do
  if [ "$(restarts)" -gt "$before" ] && [ "$(docker inspect -f '{{.State.Status}}' "$CONTAINER")" = running ]; then
    break
  fi
  sleep 2
done
after=$(restarts)
if [ "$after" -le "$before" ]; then
  echo "FAIL: container was not restarted"; docker ps -a --filter "name=$CONTAINER"; exit 1
fi
echo "   restarted automatically (restart count $before -> $after) after $(( $(date +%s) - crashed_at ))s"

echo "== Verifying the API works again (model reload can take a minute) ..."
"$PYTHON" tests/smoke_test.py --url "$SERVICE_URL" --wait 240 --output output/after_restart.jpg
echo "== Service self-recovered $(( $(date +%s) - crashed_at ))s after the crash"
