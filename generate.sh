#!/bin/bash

# Define path to the .env file
ENV_FILE=".env"
TEMPLATE_FILE=".env.template"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    # Check if template file exists to copy from
    if [ -f "$TEMPLATE_FILE" ]; then
        cp "$TEMPLATE_FILE" "$ENV_FILE"
        echo "Created '$ENV_FILE' from '$TEMPLATE_FILE'."
        echo "Please open '$ENV_FILE', fill in your values, and rerun this script."
    else
        echo "Error: '$ENV_FILE' and '$TEMPLATE_FILE' not found."
    fi
    exit 1
fi


# Check if the .env file exists
if [ -f "$ENV_FILE" ]; then
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
