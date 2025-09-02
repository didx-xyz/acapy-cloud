#!/usr/bin/env bash

set -euo pipefail

config() {
  # Store user-configured values from Docker environment
  export CONFIGURED_VUS=${VUS:-30}
  export CONFIGURED_ITERATIONS=${ITERATIONS:-10}

  # Base configuration (Docker Compose overridable)
  export VUS=${CONFIGURED_VUS}
  export ITERATIONS=${CONFIGURED_ITERATIONS}

  # Work-based configuration (derived from base values)
  export TOTAL_WORK=$((VUS * ITERATIONS))  # Total operations to perform
  export CONCURRENCY_LEVEL=${VUS}  # Parallel workers

  # Test configuration
  export SCHEMA_NAME=${SCHEMA_NAME:-"didx_acc"}
  export SCHEMA_VERSION=${SCHEMA_VERSION:-"0.1.0"}
  export HOLDER_PREFIX_TEMPLATE=${HOLDER_PREFIX_TEMPLATE:-"demoholder"}
  export TOTAL_BATCHES=${TOTAL_BATCHES:-2}

  # Default issuers if none are provided
  default_issuers=("local_pop" "local_acc")

  # Check if ISSUERS environment variable is set
  if [ -n "${ISSUERS}" ]; then
    # Split the string into an array using space as delimiter
    IFS=' ' read -ra issuers <<< "${ISSUERS}"
  else
    # Use defaults
    issuers=("${default_issuers[@]}")
  fi

  export issuers
}


should_init_issuer() {
  local issuer_prefix="$1"
  ! [[ -f "./output/${issuer_prefix}-create-issuers.jsonl" ]]
}

should_create_holders() {
  local holder_prefix="$1"
  ! [[ -f "./output/${holder_prefix}-create-holders.jsonl" ]]
}

# Helper function to build actual holder prefix from template + batch number
get_holder_prefix() {
  local batch_num="$1"
  echo "${HOLDER_PREFIX_TEMPLATE}_${batch_num}"
}

# Execution strategy functions
run_scenario_parallel() {
  local script="$1"
  export VUS=${CONFIGURED_VUS}
  export ITERATIONS=${CONFIGURED_ITERATIONS}
  run_test "$script"
}

run_scenario_serial() {
  local script="$1"
  export VUS=1
  export ITERATIONS=${TOTAL_WORK}
  run_test "$script"
}

run_scenario_concurrent() {
  local script="$1"
  export VUS=${TOTAL_WORK}
  export ITERATIONS=1
  run_test "$script"
}

init() {
  local issuer_prefix="$1"
  export ISSUER_PREFIX="${issuer_prefix}"
  xk6 run ./scenarios/bootstrap-issuer.js -e ITERATIONS=1 -e VUS=1
}

create_holders() {
  local issuer_prefix="$1"
  local batch_num="$2"

  export ISSUER_PREFIX="${issuer_prefix}"
  export HOLDER_PREFIX=$(get_holder_prefix "${batch_num}")
  export SLEEP_DURATION=0
  run_test ./scenarios/create-holders.js
}

scenario_create_invitations() {
  run_scenario_parallel ./scenarios/create-invitations.js
}

scenario_create_credentials() {
  run_scenario_parallel ./scenarios/create-credentials.js
}

scenario_create_proof_verified() {
  export IS_REVOKED=false
  run_scenario_parallel ./scenarios/create-proof.js
}

scenario_revoke_credentials() {
  run_scenario_serial ./scenarios/revoke-credentials.js
}

scenario_publish_revoke() {
  export IS_REVOKED=true

  if [[ "${FIRE_AND_FORGET_REVOCATION}" == "true" ]]; then
    run_scenario_concurrent ./scenarios/publish-revoke.js
  else
    run_scenario_parallel ./scenarios/publish-revoke.js
  fi
}

scenario_create_proof_unverified() {
  export IS_REVOKED=true
  run_scenario_parallel ./scenarios/create-proof.js
}

cleanup() {
  log "Cleaning up..."

  # Clean up holders
  for batch_num in $(seq 1 "${TOTAL_BATCHES}"); do
    export HOLDER_PREFIX=$(get_holder_prefix "${batch_num}")

    log "Cleaning up holders with prefix ${HOLDER_PREFIX}..."
    local output_flags="$(get_output_flags)"
    xk6 run ${output_flags} ./scenarios/delete-holders.js
  done

  # Clean up issuers
  for issuer in "${issuers[@]}"; do
    export ISSUER_PREFIX="${issuer}"

    log "Cleaning up issuer ${issuer}..."
    local output_flags=$(get_output_flags)
    xk6 run ${output_flags} ./scenarios/delete-issuers.js -e ITERATIONS=1 -e VUS=1
  done
}

run_batch() {
  local issuer_prefix="$1"
  local holder_batch_num="$2"

  local holder_prefix=$(get_holder_prefix "${holder_batch_num}")

  export ISSUER_PREFIX="${issuer_prefix}"
  export HOLDER_PREFIX="${holder_prefix}"

  # Check and initialize issuer if needed
  if should_init_issuer "${issuer_prefix}"; then
    log "Initializing issuer ${issuer_prefix}..."
    init "${issuer_prefix}"
  else
    log "Issuer ${issuer_prefix} already initialized, skipping..."
  fi

  # Check and create holders if needed
  if should_create_holders "${holder_prefix}"; then
    log "Creating holders for ${issuer_prefix} with prefix ${holder_prefix}..."
    create_holders "${issuer_prefix}" "${holder_batch_num}"
  else
    log "Holders already created for ${issuer_prefix} with prefix ${holder_prefix}, skipping..."
  fi

  # Run the test scenarios directly
  scenario_create_invitations
  scenario_create_credentials
  scenario_create_proof_verified
  scenario_revoke_credentials
  scenario_publish_revoke
  scenario_create_proof_unverified
}

run_collection() {
  config

  for issuer in "${issuers[@]}"; do
    for batch_num in $(seq 1 "${TOTAL_BATCHES}"); do
      log "Running batch ${batch_num} for issuer ${issuer}"
      run_batch "${issuer}" "${batch_num}"
    done
  done
}
