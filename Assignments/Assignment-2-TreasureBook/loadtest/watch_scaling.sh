#!/usr/bin/env bash
# Records the autoscaler every 10 s while the load test runs (Ctrl+C to stop).
# Output: results/scaling-<timestamp>.csv  - use it for the performance report.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
mkdir -p results
OUT="results/scaling-$(date +%Y%m%d-%H%M%S).csv"

echo "time,cpu_utilization_pct,target_pct,current_replicas,desired_replicas,running_pods" | tee "$OUT"
while true; do
  hpa=$(kubectl get hpa treasurebook-api -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization},{.spec.metrics[0].resource.target.averageUtilization},{.status.currentReplicas},{.status.desiredReplicas}')
  running=$(kubectl get pods -l app=treasurebook-api --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
  echo "$(date +%H:%M:%S),${hpa},${running}" | tee -a "$OUT"
  sleep 10
done
