#!/usr/bin/env bash
# Deprecated functions no longer used in collection_batch.sh
# These functions were used for Kubernetes restart testing but are not part of the current workflow

set -euo pipefail

# DEPRECATED: No longer used in collection_batch.sh
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

# DEPRECATED: No longer used in collection_batch.sh
restart_deployment() {
  local deployment="$1"
  log "Restarting deployment: ${deployment}"
  kubectl -n "${NAMESPACE}" rollout restart deployment "${deployment}"
  kubectl -n "${NAMESPACE}" rollout status deployment "${deployment}"
}

# DEPRECATED: No longer used in collection_batch.sh
restart_statefulset() {
  local statefulset="$1"
  log "Restarting statefulset: ${statefulset}"
  kubectl -n "${NAMESPACE}" rollout restart sts "${statefulset}"
  kubectl -n "${NAMESPACE}" rollout status sts "${statefulset}"
}

# DEPRECATED: No longer used in collection_batch.sh
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

# DEPRECATED: No longer used in collection_batch.sh
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