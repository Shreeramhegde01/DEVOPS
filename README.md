# DevOps Lab – Exercises and Assignments

![DevOps Lab CI](https://github.com/Shreeramhegde01/DEVOPS/actions/workflows/lab-ci.yml/badge.svg)
![Assignment 3 CI/CD](https://github.com/Shreeramhegde01/DEVOPS/actions/workflows/visualcraft-cicd.yml/badge.svg)

**Course:** DevOps (21IS7PEDVR) · BMS College of Engineering, Dept. of ISE
**Student:** Shreeram Hegde

Solutions to the lab exercises and assignments of the
[DevOps Lab Manual](https://github.com/SunagP/DevOps-Lab) (problem statements, notes and references are in that
repository). Every folder has working code and configuration plus a README with the steps, expected output,
answers to the questions and the screenshots to capture.

## Exercises

| # | Exercise | Topics | Folder |
|---|----------|--------|--------|
| 1 | Kubernetes Getting Started | Minikube, Pod, NodePort Service | [01-Kubernetes-Getting-Started](Exercises/01-Kubernetes-Getting-Started) |
| 2 | Deploy a Flask app on Minikube using kubectl and YAML | Dockerfile, Deployment, Service, `imagePullPolicy` | [02-Minikube-Kubectl-Flask](Exercises/02-Minikube-Kubectl-Flask) |
| 3 | Scaling a Flask App with ReplicaSets (flash sale) | ReplicaSet, scaling, self-healing, probes | [03-Minikube-Scaling-Flask-App-with-Replicasets](Exercises/03-Minikube-Scaling-Flask-App-with-Replicasets) |
| 4 | Docker Networking with multiple containers | bridge network, Docker DNS, Flask + MySQL + Redis | [04-Docker-Networking](Exercises/04-Docker-Networking) |
| 5 | Docker Security with AppArmor and Python | AppArmor profile, Docker SDK, restricted actions | [05-Docker-Security-AppArmor](Exercises/05-Docker-Security-AppArmor) |
| 6 | Real-Time Monitoring and Alerting (ZAPPTTO) | Prometheus, Grafana, alert rules, Jenkins | [06-Grafana-Realtime-Monitoring-of-Quick-Commerce-App](Exercises/06-Grafana-Realtime-Monitoring-of-Quick-Commerce-App) |
| 7 | Jenkins Installation and Introduction to CI/CD | CI concepts, Jenkins in Docker (with Python + Docker CLI) | [07-Jenkins-CI-Automation](Exercises/07-Jenkins-CI-Automation) |
| 8 | "Hello World" Jenkins Job | Freestyle job from GitHub | [08-Jenkins-Hello-World-Job](Exercises/08-Jenkins-Hello-World-Job) |
| 9 | Jenkins Multi-Stage Pipeline | Jenkinsfile: Build → Code Quality → Test → Deploy → Run → Test | [09-Jenkins-Multi-Stage-Pipeline](Exercises/09-Jenkins-Multi-Stage-Pipeline) |
| 10 | Multi-Node Kubernetes Cluster with Multiple Applications | 3-node Minikube, pod anti-affinity, node failure | [10-Minikube-Multi-Node-Multi-App-Deployment](Exercises/10-Minikube-Multi-Node-Multi-App-Deployment) |

## Assignments

| # | Assignment | Highlights | Folder |
|---|-----------|------------|--------|
| 1 (option 1) | Dockerized Multi-Container Web App with Networking and Container Management | Flask CRUD + MongoDB, Docker SDK: network, volume, inspection, health-based auto-restart | [Assignment-1A-Dockerized-Multi-Container-CRUD-App](Assignments/Assignment-1A-Dockerized-Multi-Container-CRUD-App) |
| 1 (option 2) | Secured Multi-Container App with AppArmor and Automated Health Monitoring | Login/registration + MongoDB, AppArmor via Docker SDK, health monitor with restart + alerts | [Assignment-1B-Secured-App-AppArmor-Health-Monitoring](Assignments/Assignment-1B-Secured-App-AppArmor-Health-Monitoring) |
| 2 | TreasureBook | Graph API (TAO-style nodes/edges) + MongoDB on Kubernetes, HPA 3→10 pods, load test, performance report | [Assignment-2-TreasureBook](Assignments/Assignment-2-TreasureBook) |
| 3 | VisualCraft – AI Artistic Style Service | Docker Compose, metrics gateway, Prometheus + Grafana + cAdvisor + node-exporter, resilience test, Jenkins & GitHub Actions CI/CD | [Assignment-3-VisualCraft-AI-Artistic](Assignments/Assignment-3-VisualCraft-AI-Artistic) |
| 4 | Fine-tune and deploy an LLM in Docker | Token-classification fine-tuning (course names), FastAPI, model trained during `docker build` | [Assignment-4-LLM-Course-Name-Extraction](Assignments/Assignment-4-LLM-Course-Name-Extraction) |

## Tools needed

| Tool | Used in |
|------|---------|
| Docker Desktop (Windows/macOS) or Docker Engine (Linux) | everything |
| Minikube + kubectl | Exercises 1, 2, 3, 10 · Assignment 2 |
| Python 3.10+ (`pip install docker requests`) | scripts in Exercise 5 and Assignments 1–3 |
| Linux with AppArmor (Ubuntu VM / cloud VM) | Exercise 5 · Assignment 1 option 2 |
| Jenkins (Exercise 7's image) | Exercises 6, 8, 9 · Assignment 3 |

Shell commands are written for bash (Linux, WSL or Git Bash); PowerShell differences are noted where they matter.

## Continuous integration of this repository

[`.github/workflows/lab-ci.yml`](.github/workflows/lab-ci.yml) runs on every push and exercises the labs on a Linux runner:

* unit tests of every application, lint (shellcheck, `promtool`, `kubeconform`, AppArmor parser, `docker compose config`)
* builds every Docker image
* Exercise 4 network demo, Exercise 6 monitoring stack, Assignment 1 Docker-SDK scripts
* Exercise 5 and Assignment 1 (option 2) with **real AppArmor enforcement**
* Minikube: Exercises 1, 2, 3 and Assignment 2 (including the autoscaling load test), 3-node cluster for Exercise 10
* Jenkins pipelines of Exercises 8, 9 and 6 executed in a real Jenkins
* Assignment 4 image build (fine-tuning) and API test

[`.github/workflows/visualcraft-cicd.yml`](.github/workflows/visualcraft-cicd.yml) is the CI/CD pipeline of Assignment 3.

## Repository layout

```
.
├── Exercises/            # lab exercises 1-10
├── Assignments/          # assignments 1-4
├── .github/workflows/    # CI for the whole repo + Assignment 3 CI/CD
├── file*.py, file*.txt,  # earlier Git branching / merge-conflict practice
│   shared.txt
└── README.md
```
