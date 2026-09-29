# Prometheus with the VisualCraft scrape config and alert rules baked in
# (works the same when deployed from Jenkins running in a container - no bind mounts needed)
FROM prom/prometheus:v2.54.1
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY alert_rules.yml /etc/prometheus/alert_rules.yml
