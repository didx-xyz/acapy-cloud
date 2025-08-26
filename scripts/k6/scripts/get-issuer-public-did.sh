#!/bin/bash

set -euo pipefail

# Configuration with defaults
SLEEP_INTERVAL=${SLEEP_INTERVAL:-5}
ISSUER_OUTPUT_FILE=${ISSUER_OUTPUT_FILE:-"output/issuer-create-issuers.jsonl"}
CLOUDAPI_URL=${CLOUDAPI_URL:-"http://cloudapi.127.0.0.1.nip.io"}

# Script metadata
SCRIPT_NAME="get-issuer-public-did"
START_TIME=$(date +%s)
REQUEST_COUNT=0

# Logging functions
log() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] INFO: $*"
}

error() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] ERROR: $*" >&2
}

warn() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] WARN: $*" >&2
}

# Signal handler for graceful shutdown
cleanup() {
    local duration=$(($(date +%s) - START_TIME))
    log "Script interrupted. Total requests: ${REQUEST_COUNT}, Duration: ${duration}s"
    exit 0
}

# Check dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        error "Missing required dependencies: ${missing_deps[*]}"
        error "Please install: sudo apt-get install ${missing_deps[*]} (Ubuntu/Debian) or brew install ${missing_deps[*]} (macOS)"
        exit 1
    fi
}

# Extract access token from issuer JSONL file
get_access_token() {
    if [ ! -f "${ISSUER_OUTPUT_FILE}" ]; then
        error "Issuer output file not found: ${ISSUER_OUTPUT_FILE}"
        exit 1
    fi
    
    if [ ! -r "${ISSUER_OUTPUT_FILE}" ]; then
        error "Cannot read issuer output file: ${ISSUER_OUTPUT_FILE}"
        exit 1
    fi
    
    # Read first line and extract access_token
    local access_token
    access_token=$(head -n1 "${ISSUER_OUTPUT_FILE}" | jq -r '.access_token // empty')
    
    if [ -z "${access_token}" ] || [ "${access_token}" = "null" ]; then
        error "Could not extract access_token from ${ISSUER_OUTPUT_FILE}"
        error "Expected JSON format with 'access_token' field"
        exit 1
    fi
    
    echo "${access_token}"
}

# Make HTTP request to get issuer public DID
get_public_did() {
    local access_token="$1"
    local url="${CLOUDAPI_URL}/tenant/v1/wallet/dids/public"
    
    REQUEST_COUNT=$((REQUEST_COUNT + 1))
    
    log "Request #${REQUEST_COUNT}: Calling ${url}"
    
    local http_code
    local response_body
    local curl_exit_code=0
    
    # Make the HTTP request with timeout and capture response
    response_body=$(curl -s \
        --max-time 30 \
        --write-out "%{http_code}" \
        --header "x-api-key: ${access_token}" \
        --header "Content-Type: application/json" \
        "${url}" 2>/dev/null) || curl_exit_code=$?
    
    if [ ${curl_exit_code} -ne 0 ]; then
        error "Request #${REQUEST_COUNT}: curl failed with exit code ${curl_exit_code}"
        return 1
    fi
    
    # Extract HTTP status code (last 3 characters)
    http_code="${response_body: -3}"
    response_body="${response_body%???}"
    
    log "Request #${REQUEST_COUNT}: HTTP ${http_code}"
    
    if [ "${http_code}" = "200" ]; then
        # Try to parse and show DID info if response contains JSON
        local did_info
        did_info=$(echo "${response_body}" | jq -r '.result.did // .did // "No DID found in response"' 2>/dev/null || echo "Invalid JSON response")
        log "Request #${REQUEST_COUNT}: Success - DID: ${did_info}"
    else
        warn "Request #${REQUEST_COUNT}: HTTP ${http_code} - Response: ${response_body}"
    fi
    
    return 0
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Continuously polls the issuer public DID endpoint while k6 is running.

Configuration via environment variables:
  SLEEP_INTERVAL      Sleep time between requests in seconds (default: 5)
  ISSUER_OUTPUT_FILE  Path to issuer JSONL output file (default: output/issuer-create-issuers.jsonl)
  CLOUDAPI_URL        Base URL for the Cloud API (default: http://cloudapi.127.0.0.1.nip.io)

Examples:
  $0                                                    # Use all defaults
  SLEEP_INTERVAL=10 $0                                  # 10 second intervals
  ISSUER_OUTPUT_FILE=output/my-issuer.jsonl $0          # Custom issuer file

Press Ctrl+C to stop gracefully.
EOF
}

# Main function
main() {
    # Handle help flag
    if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
        usage
        exit 0
    fi
    
    log "Starting ${SCRIPT_NAME} monitoring"
    log "Configuration:"
    log "  SLEEP_INTERVAL: ${SLEEP_INTERVAL}s"
    log "  ISSUER_OUTPUT_FILE: ${ISSUER_OUTPUT_FILE}"
    log "  CLOUDAPI_URL: ${CLOUDAPI_URL}"
    
    # Setup signal handler
    trap cleanup SIGINT SIGTERM
    
    # Check dependencies
    check_dependencies
    
    # Get access token
    local access_token
    access_token=$(get_access_token)
    log "Access token loaded successfully"
    
    # Main monitoring loop
    while true; do
        if get_public_did "${access_token}"; then
            log "Sleeping for ${SLEEP_INTERVAL} seconds..."
        else
            warn "Request failed, continuing after sleep..."
        fi
        
        sleep "${SLEEP_INTERVAL}"
    done
}

main "$@"
