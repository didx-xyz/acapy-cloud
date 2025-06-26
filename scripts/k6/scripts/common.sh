#!/usr/bin/env bash
set -euo pipefail
# Source the configuration file
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

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
  else
    echo ""
  fi
}

run_test() {
  local test_script="$1"
  local output_flags=$(get_output_flags)
  xk6 run "${output_flags}" "${test_script}"
  local exit_code=$?
  if [[ ${exit_code} -ne 0 ]]; then
    echo "Test ${test_script} failed with exit code ${exit_code}" >&2
    return 1
  fi
}

get_resource_type() {
  local resource_name="$1"

  if kubectl -n "${NAMESPACE}" get deployment "${resource_name}" >/dev/null 2>&1; then
    echo "deployment"
    return 0
  elif kubectl -n "${NAMESPACE}" get statefulset "${resource_name}" >/dev/null 2>&1; then
    echo "statefulset"
    return 0
  else
    return 1
  fi
}

restart_deployment() {
  local deployment="$1"
  log "Restarting deployment: ${deployment}"
  kubectl -n "${NAMESPACE}" rollout restart deployment "${deployment}"
  kubectl -n "${NAMESPACE}" rollout status deployment "${deployment}"
}

restart_statefulset() {
  local statefulset="$1"
  log "Restarting statefulset: ${statefulset}"
  kubectl -n "${NAMESPACE}" rollout restart sts "${statefulset}"
  kubectl -n "${NAMESPACE}" rollout status sts "${statefulset}"
}

restart_resource() {
  local resource_name="$1"
  local resource_type=$(get_resource_type "${resource_name}")

  case "${resource_type}" in
    "deployment")
      restart_deployment "${resource_name}"
      ;;
    "statefulset")
      restart_statefulset "${resource_name}"
      ;;
    *)
      err "Resource ${resource_name} not found or not a deployment/statefulset"
      ;;
  esac
}

run_ha_iterations() {
  local resources="$1"
  local scenario_func="$2"

  for ((i = 1; i <= HA_TEST_ITERATIONS; i++)); do
    log "Starting HA test iteration $i of ${HA_TEST_ITERATIONS}"
    ${scenario_func} &
    local scenario_pid=$!

    if [[ -n "${resources}" ]]; then
      for ((j = 1; j <= RESTART_ITERATIONS; j++)); do
        local resource_pids=()
        for resource in ${resources}; do
          restart_resource "${resource}" &
          resource_pids+=($!)
        done

        for pid in "${resource_pids[@]}"; do
          wait "${pid}"
          if [[ $? -ne 0 ]]; then
            wrn "A resource failed to restart" >&2
            kill "${scenario_pid}"
            return 1
          fi
        done
      done

      # Check if scenario is still running after resources restart
      if kill -0 "${scenario_pid}" 2>/dev/null; then
        log "Scenario is still running after all resources were restarted"
      else
        wrn "WARNING: Scenario completed too quickly, before all resources were restarted"
      fi
    else
      log "No stack specified. Skipping restarts."
    fi

    wait "${scenario_pid}"
    if [[ $? -ne 0 ]]; then
      err "Scenarios failed with exit code $?" >&2
      return 1
    fi
    log "Completed tests for iteration $i"
  done
}
