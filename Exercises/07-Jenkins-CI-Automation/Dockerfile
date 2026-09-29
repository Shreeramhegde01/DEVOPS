# Jenkins LTS + the tools the lab pipelines need:
#   python3 / pip / venv          -> Exercise 6 & 9 and Assignment 3 run Python builds and tests
#   docker CLI + compose plugin   -> pipelines that build and run containers, using the host's Docker
#                                    daemon through the mounted /var/run/docker.sock
FROM jenkins/jenkins:lts

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         python3 python3-pip python3-venv curl ca-certificates gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
         > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*
USER jenkins
