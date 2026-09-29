# Exercise 7 – Introduction to Continuous Integration (CI) and Jenkins Installation

## What is Continuous Integration?
Continuous Integration is the practice of merging every developer's changes into a shared repository many times a
day. **Every commit triggers an automated build and automated tests**, so integration problems are found within
minutes instead of at release time.

| Key feature | What it means |
|-------------|---------------|
| Frequent code integration | Small commits pushed to the shared repo several times a day |
| Automated builds | Each push triggers a build (compile, resolve dependencies, package) |
| Automated testing | Unit / integration tests run on every build |
| Immediate feedback | Developers see pass/fail within minutes and fix it while the change is fresh |

**Benefits:** early bug detection (cheaper fixes), better collaboration, faster development cycles and
higher code quality (tests block regressions).

**How CI works:** developer pushes to Git → the CI server detects the change → build → tests → feedback
(success/failure, reports, notifications).

## CI/CD tools

| Tool | Highlights | Best for |
|------|-----------|----------|
| **Jenkins** | Open source, self-hosted, 1800+ plugins, Groovy pipelines (`Jenkinsfile`) | Any stack, full control |
| GitHub Actions | YAML workflows in the repo, big marketplace of actions | Repos on GitHub (used by this repo's `.github/workflows`) |
| GitLab CI/CD | Built into GitLab, `.gitlab-ci.yml`, Auto DevOps | Teams on GitLab |
| CircleCI | Cloud, container-based, parallelism and caching | Containerised workflows |
| Travis CI | Simple YAML, popular with open source | Small / OSS projects |
| Bamboo | Atlassian, integrates with Jira / Bitbucket | Atlassian shops |
| TeamCity | JetBrains, detailed build history, many runners | Enterprise setups |
| Azure Pipelines | Azure DevOps, YAML or classic editor | Azure users |
| Spinnaker | Multi-cloud continuous delivery, canary / blue-green | Complex cloud deployments |
| Buildkite | Cloud control plane + self-hosted agents | Security-sensitive teams |
| Drone | Every step runs in a container | Container-first teams |

## Jenkins
Jenkins is an open-source automation server that builds, tests and deploys software (CI **and** CD).

| Concept | Meaning |
|---------|---------|
| Job / Project | A task Jenkins runs (Freestyle job, Pipeline, ...) |
| Build | One execution of a job (#1, #2, ...) with console output and status |
| Pipeline | Stages (Build → Test → Deploy) defined as code in a `Jenkinsfile` |
| Plugin | Extends Jenkins (Git, Pipeline, Docker, ...) |
| Node / Agent | Machine that executes builds (controller + agents) |

## Install Jenkins

### Option A – plain image (as in the lab manual)
```bash
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts
```
`-p 8080:8080` exposes the web UI, `-p 50000:50000` the agent port, and the `jenkins_home` volume keeps jobs across restarts.

### Option B – lab image with Python + Docker CLI (recommended for Exercises 6, 8, 9 and Assignment 3)
The stock image has no `python3` and no `docker` CLI, so the pipelines in Exercises 6/9 fail with
`python3: not found` / `docker: not found`. This folder's `Dockerfile` adds both, and `docker-compose.yml` mounts the
host's Docker socket so pipelines can build and run containers.
```bash
docker rm -f jenkins 2>/dev/null        # remove an Option-A container if you created one
docker compose up -d --build
```

### Unlock Jenkins
```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
# 060a3736329e4533ab8e4428ffcc9619
```
1. Open **http://localhost:8080** and paste the password (*Unlock Jenkins*).
2. **Install suggested plugins** (includes Pipeline and Git).
3. Create the first admin user → *Save and Finish* → **Start using Jenkins**.

### Verify the tools inside Jenkins (Option B)
```bash
docker exec jenkins python3 --version       # Python 3.x
docker exec jenkins docker version          # client + server (host's daemon)
docker exec jenkins docker compose version
```

## Screenshots to capture
1. `docker ps` showing the `jenkins` container.
2. *Unlock Jenkins* page.
3. *Getting Started* (plugin installation).
4. Jenkins dashboard after login.

## Next
* Exercise 8 – first Freestyle "Hello World" job from GitHub
* Exercise 9 – multi-stage Pipeline (Build → Test → Deploy)
