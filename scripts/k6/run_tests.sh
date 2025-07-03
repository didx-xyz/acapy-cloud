#!/bin/sh

source ./env-deprecated.sh

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

should_create_holders() {
  local holder_prefix="$1"
  ! [[ -f "./output/${holder_prefix}-create-holders.jsonl" ]]
}

# Single issuer, multiple holder tests
export MULTI_ISSUERS=false
xk6 run ./scenarios/bootstrap-issuer.js -e ITERATIONS=1 -e VUS=1
if should_create_holders "${HOLDER_PREFIX}"; then
  run_test ./scenarios/create-holders.js
fi
run_test ./scenarios/create-invitations.js
run_test ./scenarios/create-credentials.js
run_test ./scenarios/create-proof.js
export ITERATIONS=$((ITERATIONS * VUS)) # revoke sequentially
export VUS=1
export USE_AUTO_PUBLISH=true
run_test ./scenarios/revoke-credentials.js
source ./env.sh # concurrent
# run_test ./scenarios/publish-revoke.js
export IS_REVOKED=true
run_test ./scenarios/create-proof.js

run_test ./scenarios/delete-holders.js
export VUS=1 # delete single issuer - TODO: improve this
export ITERATIONS="${NUM_ISSUERS}"
run_test ./scenarios/delete-issuers.js

# # Multiple issuers tests
source ./env.sh # concurrent
export MULTI_ISSUERS=true
run_test ./scenarios/create-issuers.js
# run_test ./scenarios/create-creddef.js
run_test ./scenarios/delete-issuers.js
