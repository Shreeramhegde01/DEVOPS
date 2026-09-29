#!/usr/bin/env bash
# Starts the Exercise 7 Jenkins image (plus the Pipeline and Git plugins, setup wizard skipped) for CI.
set -euo pipefail

docker build -t devops-lab/jenkins:lts Exercises/07-Jenkins-CI-Automation
printf 'FROM devops-lab/jenkins:lts\nRUN jenkins-plugin-cli --plugins workflow-aggregator git\n' \
  | docker build -t devops-lab/jenkins-ci -

docker run -d --name jenkins -u root \
  -p 8080:8080 -p 5000:5000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --add-host host.docker.internal:host-gateway \
  -e JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
  devops-lab/jenkins-ci

echo "Waiting for Jenkins ..."
for _ in $(seq 1 120); do
  if curl -sf http://localhost:8080/api/json > /dev/null; then
    echo "Jenkins is up"
    docker exec jenkins sh -c 'python3 --version && docker --version && docker compose version'
    exit 0
  fi
  sleep 2
done
docker logs --tail 50 jenkins
exit 1
