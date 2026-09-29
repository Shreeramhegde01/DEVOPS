# Exercise 8 – Creating a "Hello World" Jenkins Job

**Objective:** put a shell script on GitHub and create a Jenkins job that pulls it from GitHub and runs it.

## Files

| File | Purpose |
|------|---------|
| `hello-world.sh` | The script Jenkins runs |
| `Jenkinsfile` | Optional pipeline version of the same job |

> The lab manual creates a separate repository `devops-sample-code`. Here the script lives in this lab repository
> (`https://github.com/Shreeramhegde01/DEVOPS`), so all lab work stays in one place. The Jenkins job simply points at
> this repo and runs the script from its folder.

## Part 1 – Script on GitHub

### (1) Personal Access Token
GitHub → *Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token*,
give it *Contents: Read and write* on this repository. Git asks for it instead of a password when you push.

### (2) Create the script
```bash
cat > hello-world.sh <<'EOF'
#!/bin/bash
echo "Hello, Jenkins!"
EOF
chmod +x hello-world.sh
```

### (3)–(6) Commit and push
```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"

git add Exercises/08-Jenkins-Hello-World-Job/hello-world.sh
git status
# Changes to be committed:
#         new file:   Exercises/08-Jenkins-Hello-World-Job/hello-world.sh
git commit -m "Add hello-world.sh"
git push origin main
# Username for 'https://github.com': <your-GitHub-account>
# Password for 'https://...@github.com': <paste the PAT>
```

### (7) Verify
Open the repository on GitHub → `Exercises/08-Jenkins-Hello-World-Job/hello-world.sh`.

## Part 2 – Jenkins Freestyle job
Prerequisite: Jenkins running (Exercise 7) → http://localhost:8080.

1. **New Item** → name `HelloWorld` → **Freestyle project** → OK.
2. **General → Description:** `Hello World! Jenkins job.`
3. **Source Code Management → Git**
   * Repository URL: `https://github.com/Shreeramhegde01/DEVOPS.git`
   * Branch Specifier: `*/main`
4. **Build Steps → Add build step → Execute shell:**
   ```bash
   sh Exercises/08-Jenkins-Hello-World-Job/hello-world.sh
   ```
5. **Save** → **Build Now**.
6. **Build History → #1 → Console Output:**
   ```
   Started by user Admin
   Running as SYSTEM
   Building in workspace /var/jenkins_home/workspace/HelloWorld
   The recommended git tool is: NONE
   Cloning the remote Git repository
   Cloning repository https://github.com/Shreeramhegde01/DEVOPS.git
   ...
   [HelloWorld] $ /bin/sh -xe /tmp/jenkins1281930102.sh
   + sh Exercises/08-Jenkins-Hello-World-Job/hello-world.sh
   Hello, Jenkins!
   Job: HelloWorld | Build: #1 | Host: 3ce8ccb39ac5 | Mon Sep 29 10:15:02 UTC 2026
   Finished: SUCCESS
   ```

### Optional – build on every push
*Build Triggers → Poll SCM* with schedule `H/2 * * * *`: Jenkins checks GitHub every 2 minutes and builds when a
new commit appears. (A GitHub webhook is faster but needs Jenkins to be reachable from the internet.)

### Optional – as a Pipeline
**New Item → Pipeline** → *Pipeline script from SCM* → same repo → Script Path
`Exercises/08-Jenkins-Hello-World-Job/Jenkinsfile`.

## Screenshots to capture
1. The script on GitHub.
2. Job configuration (SCM + Execute shell).
3. Console Output with `Hello, Jenkins!` and `Finished: SUCCESS`.
