#!/usr/bin/env bash
set -euo pipefail
# Configuration file (config.sh) removed as it's no longer needed by collection_batch.sh workflow

#------------------------------------------------------------------------------
# Declare functions
#------------------------------------------------------------------------------
# A function to print out error, log and warning messages along with other status information
# Copied from https://google-styleguide.googlecode.com/svn/trunk/shell.xml#STDOUT_vs_STDERR
err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: ERROR: $@" >&2
  exit
}

log() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: INFO: $@" >&1
}

wrn() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: WARNING: $@" >&1
}

get_output_flags() {
  if [[ "${ENABLE_STATSD:-false}" == "true" ]]; then
    echo "-o output-statsd"
  fi
}

run_test() {
  local test_script="$1"
  local output_flags=$(get_output_flags)
  if [[ -n "${output_flags}" ]]; then
    xk6 run ${output_flags} "${test_script}"
  else
    xk6 run "${test_script}"
  fi
  local exit_code=$?
  if [[ ${exit_code} -ne 0 ]]; then
    echo "Test ${test_script} failed with exit code ${exit_code}" >&2
    return 1
  fi
}

# Deprecated functions moved to common-deprecated.sh
# These functions are no longer used in collection_batch.sh
