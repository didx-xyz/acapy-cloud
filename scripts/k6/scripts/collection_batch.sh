#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

config() {
  # Global test configuration
  export BASE_VUS=${BASE_VUS:-30}
  export BASE_ITERATIONS=${BASE_ITERATIONS:-10}
  export VUS=${BASE_VUS}
  export ITERATIONS=${BASE_ITERATIONS}
  export SCHEMA_NAME=${SCHEMA_NAME:-"didx_acc"}
  export SCHEMA_VERSION=${SCHEMA_VERSION:-"0.1.0"}
  export BASE_HOLDER_PREFIX=${BASE_HOLDER_PREFIX:-"demoholder"}
  export TOTAL_BATCHES=${TOTAL_BATCHES:-2}  # New configuration parameter
  export DENOMINATOR=${DENOMINATOR:-3}
  export FACTOR=${FACTOR:-1}
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

divide_vus() {
  local base_vus=$1
  local base_iters=$2
  local denominator=$3

  export VUS=$((base_vus / denominator))
  export ITERATIONS=$((base_iters * denominator))

  log "Recalculated VUs - VUs: ${VUS}, Iterations: ${ITERATIONS}"
}

multiply_vus() {
  local base_vus=$1
  local base_iters=$2
  local factor=$3

  export VUS=$((base_vus * factor))
  export ITERATIONS=$((base_iters / factor))

  log "Recalculated VUs - VUs: ${VUS}, Iterations: ${ITERATIONS}"
}

should_init_issuer() {
  local issuer_prefix="$1"
  ! [[ -f "./output/${issuer_prefix}-create-issuers.jsonl" ]]
}

should_create_holders() {
  local holder_prefix="$1"
  ! [[ -f "./output/${holder_prefix}-create-holders.jsonl" ]]
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
  export SLEEP_DURATION=0
  run_test ./scenarios/create-holders.js
}

scenario_create_invitations() {
  run_test ./scenarios/create-invitations.js
}

scenario_create_credentials() {
  local original_vus=${BASE_VUS}
  local original_iters=${BASE_ITERATIONS}

  divide_vus "${original_vus}" "${original_iters}" "${DENOMINATOR}"

  run_test ./scenarios/create-credentials.js
}

scenario_create_proof_verified() {
  local original_vus=${BASE_VUS}
  local original_iters=${BASE_ITERATIONS}

  multiply_vus "${original_vus}" "${original_iters}" "${FACTOR}"
  run_test ./scenarios/create-proof.js
}

scenario_revoke_credentials() {
  local iterations=$((ITERATIONS * VUS))
  local vus=1
  export VUS="${vus}"
  export ITERATIONS="${iterations}"
  run_test ./scenarios/revoke-credentials.js
}

scenario_publish_revoke() {
  export IS_REVOKED=true

  local original_vus=${BASE_VUS}
  local original_iters=${BASE_ITERATIONS}

  # Adjust VUs if FIRE_AND_FORGET_REVOCATION is true
  local vus=${original_vus}
  if [[ "${FIRE_AND_FORGET_REVOCATION}" == "true" ]]; then
    vus=$((original_vus * original_iters))
    iters=1
  else
    iters=$original_iters
  fi

  local output_flags=$(get_output_flags)
  xk6 run ${output_flags} ./scenarios/publish-revoke.js -e ITERATIONS="${iters}" -e VUS="${vus}"
}

scenario_create_proof_unverified() {
  export IS_REVOKED=true
  local original_vus=${BASE_VUS}
  local original_iters=${BASE_ITERATIONS}

  multiply_vus "${original_vus}" "${original_iters}" "${FACTOR}"
  run_test ./scenarios/create-proof.js
}

cleanup() {
  log "Cleaning up..."

  # Clean up holders
  for batch_num in $(seq 1 "${TOTAL_BATCHES}"); do
    local holder_prefix="${BASE_HOLDER_PREFIX}_${batch_num}k"
    export HOLDER_PREFIX="${holder_prefix}"

    log "Cleaning up holders with prefix ${holder_prefix}..."
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

  # Run the test scenarios directly
  scenario_create_invitations
  scenario_create_credentials
  scenario_create_proof_verified
  export USE_AUTO_PUBLISH=false
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
