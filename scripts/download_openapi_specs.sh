#!/bin/bash

# Base URLs
BASE_URL="http://cloudapi.127.0.0.1.nip.io"

# Declare an associative array with endpoints and prefixes
declare -A ENDPOINTS=(
  ["tenant-admin/openapi.json"]="tenant-admin-"
  ["tenant-admin/openapi.yaml"]="tenant-admin-"
  ["tenant/openapi.json"]="tenant-"
  ["tenant/openapi.yaml"]="tenant-"
)

# Directory to store downloaded files
OUTPUT_DIR="docs/openapi"
mkdir -p "$OUTPUT_DIR"

# Loop through endpoints and download each file
for ENDPOINT in "${!ENDPOINTS[@]}"; do
  PREFIX=${ENDPOINTS[$ENDPOINT]}
  FILENAME="${PREFIX}$(basename "$ENDPOINT")"
  FILEPATH="$OUTPUT_DIR/$FILENAME"
  TEMPFILE="${FILEPATH}.tmp"

  echo "Downloading: $BASE_URL/$ENDPOINT -> $FILEPATH"
  curl -s -o "$FILEPATH" "$BASE_URL/$ENDPOINT"

  if [[ $? -eq 0 ]]; then
    echo "Downloaded successfully: $FILEPATH"

    # Format JSON files
    if [[ "$FILENAME" == *.json ]]; then
      jq . "$FILEPATH" > "$TEMPFILE" && mv "$TEMPFILE" "$FILEPATH"
      echo "Formatted JSON: $FILEPATH"
    fi

    # Format YAML files
    if [[ "$FILENAME" == *.yaml ]]; then
      yq . "$FILEPATH" > "$TEMPFILE" && mv "$TEMPFILE" "$FILEPATH"
      echo "Formatted JSON: $FILEPATH"
    fi

    # Remove temporary file if it exists
    if [[ -f "$TEMPFILE" ]]; then
      rm "$TEMPFILE"
    fi

  else
    echo "Failed to download: $BASE_URL/$ENDPOINT"
  fi
done

echo "All downloads completed!"
