#!/bin/bash

# Ensure your local environment parameters load
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "Error: $ENV_FILE file not found."
    exit 1
fi

CURL_URL="${LITELLM_BASE_URL}/models"

RESPONSE=$(curl -s -X GET "${CURL_URL}" \
  -H "Authorization: Bearer ${LITELLM_API_KEY}" \
  -H "Content-Type: application/json" \
)

echo "GET ${CURL_URL}"
echo "RESPONSE:"
echo "-------------------------------------------"
echo "${RESPONSE}"
