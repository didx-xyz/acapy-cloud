#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

config() {
  export VUS=1
  export ITERATIONS=100
  export HOLDER_PREFIX="k6_holder_holder"
  export SLEEP_DURATION=1
}

init() {
  log "Initializing..."
}

scenario() {
  run_test ./scenarios/create-holders.js
}

cleanup() {
  log "Cleaning up..."
  xk6 run --out statsd ./scenarios/delete-holders.js
}

run_collection() {
  local deployments="$1"

  config
  init
  run_ha_iterations "${deployments}" scenario
  cleanup
}
