#!/usr/bin/env bash
# Creates a Jenkins Pipeline job that loads a Jenkinsfile from this GitHub repository ("Pipeline script from SCM",
# pinned to the commit being tested), runs it and waits for the result.
# Usage: jenkins_run.sh <job-name> <Jenkinsfile path in the repo>
set -euo pipefail
JOB="$1"
SCRIPT_PATH="$2"
JENKINS=http://localhost:8080
REPO_URL="https://github.com/${GITHUB_REPOSITORY}.git"
COOKIES=$(mktemp)

CRUMB=$(curl -sf -c "$COOKIES" "$JENKINS/crumbIssuer/api/json" \
  | python3 -c 'import sys, json; d = json.load(sys.stdin); print(d["crumbRequestField"] + ":" + d["crumb"])')

cat > "/tmp/$JOB.xml" <<EOF
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>CI run of ${SCRIPT_PATH}</description>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig><url>${REPO_URL}</url></hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches><hudson.plugins.git.BranchSpec><name>${GITHUB_SHA}</name></hudson.plugins.git.BranchSpec></branches>
    </scm>
    <scriptPath>${SCRIPT_PATH}</scriptPath>
    <lightweight>false</lightweight>
  </definition>
</flow-definition>
EOF

curl -sf -b "$COOKIES" -H "$CRUMB" -H "Content-Type: application/xml" \
  --data-binary "@/tmp/$JOB.xml" "$JENKINS/createItem?name=$JOB"
curl -sf -b "$COOKIES" -H "$CRUMB" -X POST "$JENKINS/job/$JOB/build"
echo "Started $JOB ($SCRIPT_PATH)"

result=QUEUED
for _ in $(seq 1 360); do
  result=$(curl -s "$JENKINS/job/$JOB/1/api/json" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get("result") or "RUNNING")
except ValueError:
    print("QUEUED")')
  case "$result" in RUNNING|QUEUED) sleep 5 ;; *) break ;; esac
done

curl -s "$JENKINS/job/$JOB/1/consoleText" > "/tmp/$JOB-console.txt"
echo "===== $JOB: $result ====="
if [ "$result" != "SUCCESS" ]; then
  tail -n 100 "/tmp/$JOB-console.txt"
  tail -n 80 "/tmp/$JOB-console.txt" | bash .github/scripts/notice.sh "Jenkins $JOB FAILED (console tail)"
  exit 1
fi
grep -E '^\[Pipeline\] \{ \(|Hello, Jenkins|Response:|Pipeline completed|PASS|Finished:' "/tmp/$JOB-console.txt" \
  | bash .github/scripts/notice.sh "Jenkins $JOB: $result"
