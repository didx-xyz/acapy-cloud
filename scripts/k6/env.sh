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
