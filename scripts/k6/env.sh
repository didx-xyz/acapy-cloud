#!/bin/bash
# Source secret if it exists
if [ -f "./.env.local" ]; then
  source ./.env.local
fi

export K6_STATSD_ENABLE_TAGS=true
export K6_STATSD_PUSH_INTERVAL=5
export SKIP_DELETE_ISSUERS=true
export VUS=5
export ITERATIONS=2
export ISSUER_PREFIX=k6_issuer
export HOLDER_PREFIX=k6_holder
export SCHEMA_PREFIX=k6_schema
export NUM_ISSUERS=2
export SCHEMA_NAME=k6_schema
export SCHEMA_VERSION=1.0
