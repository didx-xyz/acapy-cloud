#!/bin/bash

set -e

echo "🔍 Looking for multitenant-agent pod..."

# Get the multitenant-agent pod name
POD_NAME=$(kubectl get pods --no-headers | grep "^multitenant-agent-" | awk '{print $1}' | head -1)

if [ -z "$POD_NAME" ]; then
    echo "❌ No multitenant-agent pod found!"
    exit 1
fi

echo "✅ Found pod: $POD_NAME"
echo "👀 Following logs and waiting for registry creation request..."

# Follow logs from now onwards and look for the specific pattern
kubectl logs -f --tail=0 "$POD_NAME" | while IFS= read -r line; do
    echo "$line"

    # Check if the line matches our pattern
    if echo "$line" | grep -q "Registering revocation registry definition"; then
        echo ""
        echo "🎯 Found registry creation request! Deleting pod..."

        # Kill the pod immediately
        kubectl delete pod "$POD_NAME" --force --grace-period=0

        echo "💀 Pod $POD_NAME has been deleted!"
        break
    fi
done

echo "✨ Script completed!"
