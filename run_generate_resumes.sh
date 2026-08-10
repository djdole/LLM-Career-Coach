#!/bin/bash

# Define path to the .env file
ENV_FILE=".env"

# Check if the .env file exists
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE..."
    # 1. Automatically export all variables defined or sourced next
    set -a
    # 2. Source the .env file
    source "$ENV_FILE"
    # 3. Disable automatic exporting
    set +a
else
    echo "Error: $ENV_FILE file not found."
    exit 1
fi

python3 scripts/generate_resumes.py --data data/resume_data.json --out generated/
