#!/bin/sh

source ./env.sh

run_test() {
  xk6 run "$1"
  local exit_code=$?
  if [ $exit_code -ne 0 ]; then
    echo "Test $3 failed with exit code $exit_code"
    echo "Deleting Holders"
    xk6 run ./scenarios/delete-holders.js
    if [ $MULTI_ISSUERS = false ]; then
      export VUS=1 # delete single issuer
      export ITERATIONS="${NUM_ISSUERS}"
    fi
    xk6 run ./scenarios/delete-issuers.js
    echo "Exiting with exit code $exit_code ..."
    exit $exit_code
  fi
}

# Single issuer, multiple holder tests
export MULTI_ISSUERS=false
run_test ./scenarios/create-holders.js
run_test ./scenarios/create-invitations.js
run_test ./scenarios/create-credentials.js
run_test ./scenarios/create-proof.js
export ITERATIONS=$((ITERATIONS * VUS)) # revoke sequentially
export VUS=1
# run_test ./scenarios/revoke-credentials.js
# source ./env.sh # concurrent
# export IS_REVOKED=true
# run_test ./scenarios/create-proof.js

run_test ./scenarios/delete-holders.js
export VUS=1 # delete single issuer - TODO: improve this
export ITERATIONS="${NUM_ISSUERS}"
run_test ./scenarios/delete-issuers.js

# Multiple issuers tests
source ./env.sh # concurrent
export MULTI_ISSUERS=true
run_test ./scenarios/create-issuers.js
run_test ./scenarios/create-creddef.js
run_test ./scenarios/delete-issuers.js
