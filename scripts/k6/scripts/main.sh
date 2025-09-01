#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

#------------------------------------------------------------------------------
# Consolidated functions from common.sh
#------------------------------------------------------------------------------
# A function to print out error, log and warning messages along with other status information
# Copied from https://google-styleguide.googlecode.com/svn/trunk/shell.xml#STDOUT_vs_STDERR
err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: ERROR: $*" >&2
  exit 1
}

log() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: INFO: $*"
}

wrn() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: WARNING: $*"
}

get_output_flags() {
  if [[ "${ENABLE_STATSD:-false}" == "true" ]]; then
    echo "-o output-statsd"
  fi
}

run_test() {
  local test_script="$1"
  local output_flags
  output_flags=$(get_output_flags)
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


usage() {
  cat <<EOF
Usage: $(basename "$0") [-C]
  -C             Run only the cleanup function
EOF
  exit 1
}

main() {
  local cleanup_only=false

  while getopts ":C" opt; do
    case ${opt} in
    C) cleanup_only=true ;;
    *) usage ;;
    esac
  done

  # Source the batch script directly
  source "${SCRIPT_DIR}/batch.sh"

  if ${cleanup_only}; then
    echo "Running cleanup only..."
    config
    cleanup
  else
    # Run the full batch collection
    run_collection
  fi
}

main "$@"
