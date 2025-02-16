#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

config() {
  # Global test configuration
  export BASE_VUS=${BASE_VUS:-30}
  export BASE_ITERATIONS=${BASE_ITERATIONS:-10}
  export VUS=${BASE_VUS}
  export ITERATIONS=${BASE_ITERATIONS}
  export SCHEMA_NAME="didx_acc"
  export BASE_HOLDER_PREFIX=${BASE_HOLDER_PREFIX:-"demoholder"}
  export TOTAL_BATCHES=${TOTAL_BATCHES:-2}  # New configuration parameter
  export issuers=("didxissuer_pop" "didxissuer_acc")
}

calculate_create_creds_load() {
  local base_vus=$1
  local base_iters=$2

  export VUS=$((base_vus / 2))
  export ITERATIONS=$((base_iters * 2))

  log "Adjusted load for create credentials - VUs: ${VUS}, Iterations: ${ITERATIONS}"
}

should_init_issuer() {
  local issuer_prefix="$1"
  ! [[ -f "./output/${issuer_prefix}-create-issuers.json" ]]
}

should_create_holders() {
  local holder_prefix="$1"
  ! [[ -f "./output/${holder_prefix}-create-holders.json" ]]
}

init() {
  local issuer_prefix="$1"
  export ISSUER_PREFIX="${issuer_prefix}"
  xk6 run ./scenarios/bootstrap-issuer.js -e ITERATIONS=1 -e VUS=1
}

create_holders() {
  local issuer_prefix="$1"
  local holder_prefix="$2"

  export ISSUER_PREFIX="${issuer_prefix}"
  export HOLDER_PREFIX="${holder_prefix}"
  export SLEEP_DURATION=0.1
  xk6 run -o output-statsd ./scenarios/create-holders.js
}

scenario_create_invitations() {
  run_test ./scenarios/create-invitations.js
}

scenario_create_credentials() {
  local original_vus=${BASE_VUS}
  local original_iters=${BASE_ITERATIONS}

  calculate_create_creds_load "${original_vus}" "${original_iters}"

  run_test ./scenarios/create-credentials.js
}

scenario_create_proof_verified() {
  run_test ./scenarios/create-proof.js
}

scenario_revoke_credentials() {
  local iterations=$((ITERATIONS * VUS))
  local vus=1
  xk6 run -o output-statsd ./scenarios/revoke-credentials.js -e ITERATIONS=${iterations} -e VUS=${vus}
}

scenario_create_proof_unverified() {
  export IS_REVOKED=true
  run_test ./scenarios/create-proof.js
}

cleanup() {
  log "Cleaning up..."

  # Clean up holders
  for batch_num in $(seq 1 ${TOTAL_BATCHES}); do
    local holder_prefix="${BASE_HOLDER_PREFIX}_${batch_num}k"
    export HOLDER_PREFIX="${holder_prefix}"

    log "Cleaning up holders with prefix ${holder_prefix}..."
    xk6 run -o output-statsd ./scenarios/delete-holders.js
  done

  # Clean up issuers
  for issuer in "${issuers[@]}"; do
    export ISSUER_PREFIX="${issuer}"

    log "Cleaning up issuer ${issuer}..."
    xk6 run -o output-statsd ./scenarios/delete-issuers.js -e ITERATIONS=1 -e VUS=1
  done
}

run_batch() {
  local issuer_prefix="$1"
  local holder_batch_num="$2"
  local deployments="$3"

  local holder_prefix="${BASE_HOLDER_PREFIX}_${holder_batch_num}k"

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
    create_holders "${issuer_prefix}" "${holder_prefix}"
  else
    log "Holders already created for ${issuer_prefix} with prefix ${holder_prefix}, skipping..."
  fi

  # Run the test scenarios
  run_ha_iterations "${deployments}" scenario_create_invitations
  run_ha_iterations "${deployments}" scenario_create_credentials

  export VUS=${BASE_VUS}
  export ITERATIONS=${BASE_ITERATIONS}
  run_ha_iterations "${deployments}" scenario_create_proof_verified
}

run_collection() {
  local deployments="$1"

  config

  for issuer in "${issuers[@]}"; do
    for batch_num in $(seq 1 ${TOTAL_BATCHES}); do
      log "Running batch ${batch_num} for issuer ${issuer}"
      run_batch "${issuer}" "${batch_num}" "${deployments}"
    done
  done
}
