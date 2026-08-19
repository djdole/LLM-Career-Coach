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

# 1. Auto-reparation step: Verify system dependencies before building venv
if [ ! -f "/usr/share/doc/python3.14/README.venv" ] && [ ! -d "/usr/lib/python3/dist-packages/ensurepip" ]; then
    echo "System components missing. Attempting automatic installation..."
    sudo apt update && sudo apt install python3-full -y
fi

# 2. Create the virtual environment if it does not exist or is broken
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    echo "Initializing fresh virtual environment..."
    rm -rf venv
    python3 -m venv venv
    
    # Second-pass fallback if the first apt attempt was bypassed or failed
    if [ ! -f "venv/bin/activate" ]; then
        echo "Venv failed. Retrying system package installation..."
        sudo apt update && sudo apt install python3-full -y
        rm -rf venv
        python3 -m venv venv
    fi
fi

# 3. Activate the virtual environment
source venv/bin/activate

# 4. Upgrade pip and install dependencies using the explicit venv path
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements-test.txt

# 5. Run your python application using the explicit venv path
./venv/bin/python generator.py "$@"
