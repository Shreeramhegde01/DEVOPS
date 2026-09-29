#!/usr/bin/env bash
# Runs every task of Exercise 4 end to end.
#   ./run-network-demo.sh          # run all tasks, then clean up
#   ./run-network-demo.sh --keep   # leave the containers + network running for exploration
set -euo pipefail
cd "$(dirname "$0")"

NET=my-bridge-net

# Remove leftovers of a previous run of this lab (same container / network names)
docker rm -f mysql redis flask >/dev/null 2>&1 || true
docker network rm "$NET" >/dev/null 2>&1 || true

echo "== Task 1: create a user-defined bridge network"
docker network create --driver bridge "$NET"

echo "== Task 2: verify the network"
docker network ls --filter name="$NET"

echo "== Task 3: inspect the network"
docker network inspect "$NET"

echo "== Task 4: build the Flask image and launch the three containers"
docker build -t flask-api .
# mysql exits immediately without a root password, so one is passed in
docker run -d --name mysql --net="$NET" -e MYSQL_ROOT_PASSWORD=devops-lab mysql:8.0
docker run -d --name redis --net="$NET" redis:7
docker run -d --name flask --net="$NET" -p 5001:5001 flask-api

echo "== Task 5: test connectivity from inside the flask container"
docker exec flask ping -c 2 mysql
docker exec flask ping -c 2 redis

echo "-- Container IPs on $NET:"
docker network inspect "$NET" --format '{{range .Containers}}{{.Name}} -> {{.IPv4Address}}{{"\n"}}{{end}}'

echo "-- REST API from the host (published port 5001):"
curl -sf --retry 15 --retry-connrefused --retry-delay 1 http://localhost:5001/about; echo

echo "-- Flask -> MySQL (3306) and Redis (6379) by container name (waits for MySQL to finish initialising):"
curl -sf --retry 30 --retry-all-errors --retry-delay 2 http://localhost:5001/status; echo

if [ "${1:-}" != "--keep" ]; then
  echo "== Task 6: clean up"
  docker stop mysql redis flask
  docker rm mysql redis flask
  docker network rm "$NET"
fi
