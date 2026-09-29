# Exercise 4 – Docker Networking with Multiple Containers

**Objective:** understand Docker networking and configure a multi-container application.

**Scenario:** a web application made of

* a Python Flask web server (container 1 – `flask`)
* a MySQL database (container 2 – `mysql`)
* a Redis cache (container 3 – `redis`)

all attached to one user-defined bridge network so they can find each other **by name**.

```
               host :5001
                   │  (-p 5001:5001)
┌──────────────────┼───────────── my-bridge-net (172.18.0.0/16) ─────────────┐
│   ┌──────────────▼─┐        ┌───────────────┐        ┌───────────────┐     │
│   │ flask          │ ─────► │ mysql :3306   │        │ redis :6379   │     │
│   │ 172.18.0.4     │ ───────┼───────────────┼──────► │ 172.18.0.3    │     │
│   └────────────────┘        │ 172.18.0.2    │        └───────────────┘     │
│                             └───────────────┘                              │
│              Docker embedded DNS (127.0.0.11) resolves container names     │
└────────────────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask API: `/about` (from the manual) and `/status`, which resolves `mysql` and `redis` by name and opens a TCP connection to each |
| `requirements.txt`, `Dockerfile` | `flask-api` image (includes `ping`) |
| `run-network-demo.sh` | Runs Tasks 1-6 end to end (`--keep` leaves everything running) |
| `test_app.py` | Unit tests |

## Tasks

### Task 1 – Create a bridge network
```bash
docker network create --driver bridge my-bridge-net
# 87c23b491f59...
```

### Task 2 – Verify the network
```bash
docker network ls
# NETWORK ID     NAME            DRIVER    SCOPE
# 87c23b491f59   my-bridge-net   bridge    local
```

### Task 3 – Inspect the network
```bash
docker network inspect my-bridge-net
# "Driver": "bridge", "Subnet": "172.18.0.0/16", "Gateway": "172.18.0.1", "Containers": {}
```

### Task 4 – Build the Flask image and launch the containers
```bash
docker build -t flask-api .

docker run -d --name mysql --net=my-bridge-net -e MYSQL_ROOT_PASSWORD=devops-lab mysql:8.0
docker run -d --name redis --net=my-bridge-net redis:7
docker run -d --name flask --net=my-bridge-net -p 5001:5001 flask-api
```
> The manual's `docker run ... mysql:latest` without `MYSQL_ROOT_PASSWORD` stops at once
> ("You need to specify one of MYSQL_ROOT_PASSWORD..."), so `ping mysql` would fail. That is why the password is passed.

### Task 5 – Test connectivity
```bash
docker exec -it flask bash
ping -c 2 mysql
# PING mysql (172.18.0.2) 56(84) bytes of data.
# 64 bytes from mysql.my-bridge-net (172.18.0.2): icmp_seq=1 ttl=64 time=0.078 ms
ping -c 2 redis
# 64 bytes from redis.my-bridge-net (172.18.0.3): icmp_seq=1 ttl=64 time=0.081 ms
exit

curl http://localhost:5001/about
# {"description":"This is a simple REST API built with Flask.","name":"Simple REST API","version":"1.0"}

curl http://localhost:5001/status
# {"container":"a1b2c3d4e5f6","dependencies":{"mysql":{"ip":"172.18.0.2","port":3306,"reachable":true},
#                                            "redis":{"ip":"172.18.0.3","port":6379,"reachable":true}}}
```

### Task 6 – Clean up
```bash
docker stop mysql redis flask && docker rm mysql redis flask
docker network rm my-bridge-net
```

Or run everything in one go: `./run-network-demo.sh` (Git Bash / WSL / Linux).

## Questions and answers

1. **What is the purpose of the `--net` flag in `docker run`?**
   It attaches the container to a given network (here `my-bridge-net`) instead of the default `bridge`.
2. **How do containers communicate on the same network?**
   By container name or IP. On a user-defined network Docker's embedded DNS resolves `mysql` → `172.18.0.2`.
   (The default `bridge` network has **no** name resolution, which is why we create our own.)
3. **Bridge network vs host network?**
   *Bridge* – containers get their own private subnet and talk to each other through a virtual switch; ports must be
   published to be reachable from outside ("private room with a door").
   *Host* – the container shares the host's network stack directly, with no isolation and no port mapping
   ("same room as the host").
4. **How do you expose a container's port to the host?**
   With `-p <host-port>:<container-port>`, e.g. `-p 5001:5001`.
5. **Why does the app listen on `0.0.0.0`?**
   A server bound to `127.0.0.1` inside a container only accepts connections from inside that container,
   so the published port would not work.
