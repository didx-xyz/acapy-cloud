#!/bin/bash

set -e

# Default log pattern if none provided
DEFAULT_PATTERN="Publishing revocation registry definition resource"
LOG_PATTERN="${1:-$DEFAULT_PATTERN}"

echo "🔍 Looking for multitenant-agent pod..."
echo "🎯 Monitoring for pattern: '$LOG_PATTERN'"

# Get the multitenant-agent pod name
POD_NAME=$(kubectl get pods --no-headers | grep "^multitenant-agent-" | awk '{print $1}' | head -1)

if [ -z "$POD_NAME" ]; then
    echo "❌ No multitenant-agent pod found!"
    exit 1
fi

echo "✅ Found pod: $POD_NAME"
echo "👀 Following logs and waiting for pattern match..."

# Follow logs from now onwards and look for the specific pattern
kubectl logs -f --tail=0 "$POD_NAME" | while IFS= read -r line; do
    # Check if the line matches our pattern
    if echo "$line" | grep -q "$LOG_PATTERN"; then
        echo ""
        echo "🎯 Found pattern match! Deleting pod..."

        # Kill the pod immediately
        kubectl delete pod "$POD_NAME" --force --grace-period=0

        echo "💀 Pod $POD_NAME has been deleted!"
        break
    fi
done

echo "✨ Script completed!"
