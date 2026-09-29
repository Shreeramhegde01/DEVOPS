# Sourced by every bash step of the workflows (through BASH_ENV).
# Mirrors the step's output into $CI_LOG, so a failure step can turn its tail into an annotation, and pauses
# briefly on exit so `tee` has flushed everything before the runner stops reading the step's output.
if [ -z "${CI_LOG_ACTIVE:-}" ] && [ -n "${CI_LOG:-}" ]; then
  export CI_LOG_ACTIVE=1
  exec > >(tee -a "$CI_LOG") 2>&1
  trap 'sleep 1' EXIT
fi
