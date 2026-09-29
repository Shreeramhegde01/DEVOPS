#!/bin/bash
echo "Hello, Jenkins!"
echo "Job: ${JOB_NAME:-local} | Build: #${BUILD_NUMBER:-0} | Host: $(hostname) | $(date)"
