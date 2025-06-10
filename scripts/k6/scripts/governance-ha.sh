#!/bin/bash
source ./env.sh

NAMESPACE="dev-cloudapi"
export ISSUER_PREFIX="k6_issuer_zc"
export VUS=1
export ITERATIONS=1

WEBS="governance-ga-web governance-multitenant-web governance-tenant-web governance-public-web"
AGENT="governance-ga-agent governance-multitenant-agent"
SERVICE="tails-server governance-trust-registry"
AUTH="inquisitor"
TESTS="create-issuers.js create-creddef.js"

INVALID="governance-multitenant-web governance-multitenant-agent governance-tenant-web"

# Combine all stacks into one variable
ALL="$SERVICE $AGENT $WEBS $AUTH"

# Remove INVALID deployments from ALL
for invalid in $INVALID; do
  ALL=${ALL//$invalid/}
done

# Remove any extra spaces
ALL=$(echo "$ALL" | tr -s ' ')

for STACK in ALL; do
  for TEST in ${TESTS}; do
    xk6 run -e SKIP_DELETE_ISSUERS=true -e SKIP_DELETE_HOLDERS=true ./scenarios/"${TEST}" &
    PID=$!
    for DEPLOYMENT in ${!STACK}; do
      # kubectl -n ${NAMESPACE} scale deployment ${DEPLOYMENT} --replicas=3
      kubectl -n "${NAMESPACE}" rollout restart deployment "${DEPLOYMENT}"
      kubectl -n "${NAMESPACE}" rollout status deployment "${DEPLOYMENT}" &
      declare PID_"${DEPLOYMENT//-/_}"=$!
    done
    for DEPLOYMENT in ${!STACK}; do
      DEPLOYMENT_PID_VAR="PID_${DEPLOYMENT//-/_}"
      echo "Wait for ${DEPLOYMENT_PID_VAR}..."
      wait "${!DEPLOYMENT_PID_VAR}"
    done
    echo "Wait for test phase $TEST with PID: $PID..."
    wait $PID
    echo done
  done
done

xk6 run ./scenarios/delete-issuers.js
