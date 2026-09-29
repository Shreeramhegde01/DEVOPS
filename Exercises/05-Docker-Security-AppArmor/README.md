# Exercise 5 – Docker Security with AppArmor and Python

**Objective:** secure a Docker container with an AppArmor profile, apply it with the Docker SDK for Python and
test that restricted actions really are blocked.

**Scenario:** a containerised Flask web app must not be able to read sensitive files, modify the system or start
shells, even if an attacker gets code execution inside it.

> **Needs Linux with AppArmor** – Ubuntu / Debian (native, VM or cloud VM).
> Docker Desktop on Windows/macOS does **not** support AppArmor profiles, and neither does WSL2's default kernel.

## Files

| File | Purpose |
|------|---------|
| `app.py`, `Dockerfile` | The Flask application / image `flask-apparmor` |
| `my-apparmor-profile` | AppArmor profile (goes to `/etc/apparmor.d/my-apparmor-profile`) |
| `apply_apparmor.py` | Task 4 – Docker SDK: build, run with the profile, verify it is enforced |
| `test_restricted_actions.py` | Task 5 – runs restricted actions with Docker's default profile vs. our profile and compares |

## Prerequisites
```bash
sudo apt-get update
sudo apt-get install -y apparmor-utils python3-pip
pip install docker
sudo aa-status | head -3        # "apparmor module is loaded."
```

## Task 1 & 2 – Flask app and Docker image
```bash
docker build -t flask-apparmor .
```

## Task 3 – Create and load the AppArmor profile
```bash
sudo cp my-apparmor-profile /etc/apparmor.d/my-apparmor-profile
sudo apparmor_parser -r -W /etc/apparmor.d/my-apparmor-profile
sudo aa-status | grep my-apparmor-profile           # listed under "profiles are in enforce mode"

docker run -d --name flask-secure --security-opt apparmor=my-apparmor-profile -p 5000:5000 flask-apparmor
curl http://localhost:5000
# Hello, this is a secure Flask application running inside a Docker container!
docker rm -f flask-secure
```

### What the profile does
| Rule | Effect |
|------|--------|
| `profile my-apparmor-profile flags=(attach_disconnected,mediate_deleted)` | Named profile that Docker can attach to a container |
| `network inet tcp`, `deny network raw` | App can serve HTTP; no raw sockets (no ping floods / packet sniffing) |
| `file,` then `deny ...` | Python can load its libraries, but the listed paths are blocked |
| `deny /etc/passwd`, `/etc/shadow`, `/root/**` | No reading of account data or root's home |
| `deny /etc/** wl`, `/usr/** wl`, `/var/** wl`, ... | System directories are read-only |
| `deny /{,usr/}bin/{bash,dash,sh,curl,wget,apt*} mrwklx` | No shells or download tools |
| `capability net_bind_service`, `deny capability sys_admin` | Only the capability the app needs |
| `deny mount`, `deny @{PROC}/...`, `/sys/...` | Same kernel-interface protection as Docker's default profile |

> The manual's version used `/usr/bin/python3 { ... }` as the profile header. That creates a profile named after a
> binary path, so `--security-opt apparmor=my-apparmor-profile` cannot find it. It also allowed only `/app/**`,
> which blocks the Python runtime itself. The profile here fixes both.

## Task 4 – Apply the profile with the Docker SDK
```bash
python3 apply_apparmor.py
```
Expected output:
```
Building image from Dockerfile...
[INFO] Step 1/6 : FROM python:3.11-slim
...
Running container with AppArmor profile...
Container started: f8c2a7f9b9b8

Inspecting container to verify AppArmor profile...
AppArmor profile applied (HostConfig.SecurityOpt): ['apparmor=my-apparmor-profile']
AppArmorProfile reported by Docker              : my-apparmor-profile
Kernel confinement of the Flask process (PID 1)  : my-apparmor-profile (enforce)
App response on http://localhost:5000/           : Hello, this is a secure Flask application running inside a Docker container!

Stopping the container...

RESULT: profile enforced
```

## Task 5 – Test restricted actions
```bash
python3 test_restricted_actions.py
```
Expected output:
```
Action                                             docker-default         my-apparmor-profile
------------------------------------------------------------------------------------------------
Read /etc/passwd                                   ALLOWED (exit 0)       BLOCKED (exit 1)
                                                                          -> cat: /etc/passwd: Permission denied
Write a file in /etc                               ALLOWED (exit 0)       BLOCKED (exit 1)
                                                                          -> touch: cannot touch '/etc/hacked': Permission denied
Execute /bin/bash from a shell in the container    ALLOWED (exit 0)       BLOCKED (exit 126)
                                                                          -> sh: 1: /bin/bash: Permission denied
Flask/Python process spawns /bin/sh                ALLOWED (exit 0)       BLOCKED (exit 1)
                                                                          -> PermissionError: [Errno 13] Permission denied: '/bin/sh'
Read the app's own code /app/app.py                ALLOWED (exit 0)       ALLOWED (exit 0)
App still answers HTTP on port 5000                ALLOWED (exit 0)       ALLOWED (exit 0)

RESULT: all restrictions enforced
```
The same image behaves very differently with and without the profile. The app keeps working, but everything
an attacker would try next is denied.

## Cleanup
```bash
sudo apparmor_parser -R /etc/apparmor.d/my-apparmor-profile   # unload
sudo rm /etc/apparmor.d/my-apparmor-profile
docker rmi flask-apparmor
```

## Questions and answers

1. **Purpose of AppArmor with Docker?** – A Linux kernel security module (mandatory access control) that confines what
   a container's processes may do – files, network, capabilities – adding a layer on top of namespaces and cgroups.
2. **How do AppArmor profiles secure a container?** – They state which files may be read/written/executed, which
   network families are usable and which capabilities are granted. The kernel enforces this even for root inside the container.
3. **Why restrict `/etc` and `/var`?** – `/etc` holds accounts, passwords and system configuration; `/var` holds logs
   and state. Reading them leaks information and writing them can tamper with the system or hide an attack.
4. **What else can AppArmor restrict?** – Network access (raw/packet sockets), binding ports, executing binaries,
   writing to directories, mounting filesystems, `ptrace`, loading kernel modules and capabilities such as `sys_admin`.
5. **How do you verify a profile is applied?** – `docker inspect` (`HostConfig.SecurityOpt` and `AppArmorProfile`),
   `cat /proc/1/attr/current` inside the container (`my-apparmor-profile (enforce)`), `sudo aa-status`, and by
   testing that denied actions fail – as `test_restricted_actions.py` does.
