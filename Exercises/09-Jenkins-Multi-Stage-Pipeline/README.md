# Exercise 9 – Jenkins Multi-Stage Pipeline: Deploying a Python Application

**Objective:** build a Jenkins **Pipeline** (pipeline-as-code in a `Jenkinsfile`) that builds, tests and deploys a
Python Flask application in separate stages.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask app – `Hello, Jenkins Multi-Stage Pipeline!` on port 5000 |
| `requirements.txt` | `flask==3.0.3` |
| `test_app.py` | Unit test (unittest) |
| `Jenkinsfile` | The multi-stage pipeline |

## Pipeline stages

| Stage | What it does |
|-------|--------------|
| **Build** | Creates a virtualenv and runs `pip install -r requirements.txt` |
| **Code Quality** | `flake8` lint (the "additional enhancement" from the manual) |
| **Test** | `python -m unittest discover` – the build fails if a test fails |
| **Deploy** | Copies `app.py` to `$WORKSPACE/python-app-deploy` (mock deployment directory) |
| **Run Application** | Starts the deployed app in the background with `nohup`, saves its PID |
| **Test Application** | Smoke test: `curl http://127.0.0.1:5000/` must return the expected text |
| `post` | Prints a success / failure message |

## Steps

### 1. Jenkins
Start Jenkins from Exercise 7 (**Option B** – that image already contains `python3`, `pip` and `venv`).
The *Pipeline* plugin comes with the suggested plugins.

### 2. Application code
Already in this folder (`app.py`, `requirements.txt`, `test_app.py`). Run it locally first:
```bash
pip install -r requirements.txt
python -m unittest discover -s . -v
# test_home (test_app.TestApp.test_home) ... Hello, Jenkins Multi-Stage Pipeline!
# ok
# Ran 1 test in 0.004s
# OK
```

### 3. Push to GitHub
The code and `Jenkinsfile` are part of this repository:
```bash
git add Exercises/09-Jenkins-Multi-Stage-Pipeline
git commit -m "Exercise 9: multi-stage Jenkins pipeline"
git push origin main
```

### 4. Create the pipeline job
**New Item** → name `Python-MultiStage-Pipeline` → **Pipeline** → OK.

### 5. Configure it
*Pipeline* section:
* Definition: **Pipeline script from SCM**
* SCM: **Git**, Repository URL `https://github.com/Shreeramhegde01/DEVOPS.git`, branch `*/main`
* Script Path: `Exercises/09-Jenkins-Multi-Stage-Pipeline/Jenkinsfile`
* Save.

### 6. Run
**Build Now** → the Stage View shows every stage going green. Console output (abridged):
```
Obtained Exercises/09-Jenkins-Multi-Stage-Pipeline/Jenkinsfile from git https://github.com/Shreeramhegde01/DEVOPS.git
[Pipeline] { (Build)
Creating virtual environment and installing dependencies...
Successfully installed ... flask-3.0.3 ...
[Pipeline] { (Code Quality)
+ .venv/bin/flake8 --exclude=.venv --max-line-length=120 .
[Pipeline] { (Test)
+ .venv/bin/python -m unittest discover -s . -v
test_home (test_app.TestApp.test_home) ... Hello, Jenkins Multi-Stage Pipeline!
ok
Ran 1 test in 0.004s
OK
[Pipeline] { (Deploy)
+ cp /var/jenkins_home/workspace/Python-MultiStage-Pipeline/Exercises/09-Jenkins-Multi-Stage-Pipeline/app.py /var/jenkins_home/workspace/Python-MultiStage-Pipeline/python-app-deploy/
[Pipeline] { (Run Application)
Started app with PID 5064 on port 5000
[Pipeline] { (Test Application)
Response: Hello, Jenkins Multi-Stage Pipeline!
[Pipeline] { (Declarative: Post Actions)
Pipeline completed successfully!
Finished: SUCCESS
```
With the Exercise 7 compose setup, port 5000 is published, so http://localhost:5000 also shows the deployed app.

### 7. Handling build errors (stock `jenkins/jenkins:lts` image)
If you used the plain image, the pipeline fails with `python3: not found`. Either switch to the Exercise 7 image,
or install Python inside the running container:
```bash
docker exec -it -u root jenkins bash
apt-get update
apt-get install -y python3 python3-pip python3-venv
exit
```

## Further enhancements
* Build a Docker image in the pipeline and deploy it as a container (see Exercise 6 / Assignment 3).
* Notifications: `post { failure { mail to: 'team@example.com', subject: "Build failed: ${env.JOB_NAME}", body: "${env.BUILD_URL}" } }`.
* Trigger on every push: `triggers { pollSCM('H/2 * * * *') }` or a GitHub webhook.

## Screenshots to capture
1. Pipeline job configuration (SCM + Script Path).
2. Stage View with all stages green.
3. Console Output ending in `Finished: SUCCESS`.
