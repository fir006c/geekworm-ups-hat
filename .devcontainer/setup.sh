#!/bin/bash
set -e # Interrompe lo script in caso di errori

WORKSPACE_DIR="${1:-$(pwd)}"

echo "Environment configuration..."
mkdir -p /config/custom_components
ln -sf "$WORKSPACE_DIR/custom_components/geekworm_ups" /config/custom_components/geekworm_ups
cp "$WORKSPACE_DIR/.devcontainer/start.sh" /start.sh
