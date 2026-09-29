#!/usr/bin/env bash
# Simulates flash-sale shoppers: sends N /buy requests to the flashsale-svc Service from a
# throw-away pod *inside* the cluster, then counts which pod served each request.
# (kubectl port-forward would pin every request to a single pod, so we go through the Service.)
#
# Usage: ./load-test.sh [number-of-requests]
set -euo pipefail

N="${1:-30}"

kubectl run flashsale-load --rm -i --restart=Never --quiet --image=busybox:1.36 -- \
  sh -c "for i in \$(seq 1 ${N}); do wget -qO- http://flashsale-svc/buy; echo; done" \
  | grep -o '"served_by_pod":"[^"]*"' \
  | sort | uniq -c
