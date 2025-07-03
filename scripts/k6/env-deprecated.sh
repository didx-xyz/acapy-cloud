#!/bin/bash

# StatsD/DataDog Configuration
export ENABLE_STATSD=${ENABLE_STATSD:-false}
export K6_STATSD_PUSH_INTERVAL=${K6_STATSD_PUSH_INTERVAL:-5}

# Conditional StatsD configuration
if [[ "${ENABLE_STATSD}" == "true" ]]; then
    export K6_STATSD_ENABLE_TAGS=true
    export K6_STATSD_ADDR=${K6_STATSD_ADDR:-datadog:8125}
else
    export K6_STATSD_ENABLE_TAGS=false
    unset K6_STATSD_ADDR
fi
export SKIP_DELETE_ISSUERS=true
export VUS=4
export ITERATIONS=1
export ISSUER_PREFIX=k6_issuer
export HOLDER_PREFIX=k6_holder
export SCHEMA_PREFIX=k6_schema
export NUM_ISSUERS=1
export SCHEMA_NAME=${SCHEMA_NAME:-k6_schema}
export SCHEMA_VERSION=${SCHEMA_VERSION:-1.0}
export OOB_INVITATION=true # temporary until connect via pulbic DID on Cheqd is implemented
export USE_AUTO_PUBLISH=true
