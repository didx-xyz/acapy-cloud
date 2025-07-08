#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
K6_DIR="$(dirname "${SCRIPT_DIR}")"

# Source the env file for secrets and environment variables
source "${K6_DIR}/env.sh"

#------------------------------------------------------------------------------
# Consolidated functions from common.sh
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

# Trap SIGINT to ensure k6 process is terminated
trap 'cleanup_k6' SIGINT

cleanup_k6() {
  pkill -f xk6 || true
  echo "Terminated k6 process"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") -c COLLECTION [-s STACK] [-C]
  -c COLLECTION  Specify a test collection (required)
  -s STACK       Specify a stack to restart (WEBS, AGENT, SERVICE, AUTH, or ALL)
                 If not specified, no restarts will occur.
  -C             Run only the cleanup function for the specified collection
EOF
  exit 1
}

main() {
  local stack=""
  local collection=""
  local cleanup_only=false

  # Print usage if no arguments are provided
  if [[ $# -eq 0 ]]; then
    usage
  fi

  while getopts ":s:c:C" opt; do
    case ${opt} in
    s) stack=$OPTARG ;;
    c) collection=$OPTARG ;;
    C) cleanup_only=true ;;
    *) usage ;;
    esac
  done

  # Check if collection is provided
  if [[ -z "${collection}" ]]; then
    echo "Error: Collection must be specified" >&2
    usage
  fi

  local deployments=""
  if [[ -n "${stack}" ]]; then
    case ${stack} in
    WEBS | AGENT | SERVICE | AUTH | STS | ALL) deployments="${!stack}" ;;
    *)
      echo "Error: Invalid stack specified" >&2
      usage
      ;;
    esac
  fi

  local collection_script="${SCRIPT_DIR}/collection_${collection}.sh"
  if [[ ! -f "${collection_script}" ]]; then
    echo "Error: Unknown collection '${collection}'" >&2
    exit 1
  fi

  source "${collection_script}"

  # Check if the cleanup function exists
  if ! declare -f cleanup >/dev/null; then
    echo "Error: No cleanup function found for collection '${collection}'" >&2
    exit 1
  fi

  if ${cleanup_only}; then
    echo "Running cleanup only for collection '${collection}'..."
    config
    cleanup
  else
    # Run the full collection
    run_collection "${deployments}"
  fi
}

main "$@"
