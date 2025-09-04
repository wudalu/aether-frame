#!/bin/bash
set -e

# Check if pip-tools is installed
if ! command -v pip-compile &> /dev/null; then
    echo "pip-tools not found. Installing..."
    pip install pip-tools
fi

echo "Compiling requirements..."
echo "Compiling base requirements..."
pip-compile requirements/base.in

echo "Compiling dev requirements..."
pip-compile requirements/dev.in

echo "Requirements compilation completed!"
echo "Generated files:"
echo "  - requirements/base.txt"
echo "  - requirements/dev.txt"