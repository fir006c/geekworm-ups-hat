#!/bin/bash
# Start the daemon on background (simulation mode) and keep the container running
export HW_VERSION="v2.1"
export DAEMON_PORT="8099"
export POLL_INTERVAL="10"
export SHUTDOWN_VOLTAGE="0"
export SHUTDOWN_CAPACITY="0"
export SHUTDOWN_DELAY="10"
export BUZZER_ON_AC_LOSS="false"

# Find the workspace directory (fall-back on /workspaces/geekworm-ups-hat if empty)
WORKSPACE_DIR="${CONTAINER_WORKSPACE_FOLDER:-/workspaces/geekworm-ups-hat}"

echo "Using workspace directory: $WORKSPACE_DIR"

echo "Starting Geekworm UPS HAT daemon in simulation mode..."

APP_DIR="$WORKSPACE_DIR/ha-addon-geekworm"

if [ -f "$APP_DIR/geekworm_daemon.py" ]; then
    python3 "$APP_DIR/geekworm_daemon.py" &
    echo "Geekworm UPS HAT daemon started with PID $!"
else
    echo "ERROR: geekworm_daemon.py not found in $APP_DIR"
    exit 1
fi
