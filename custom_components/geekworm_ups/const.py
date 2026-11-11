"""Constants for the Geekworm UPS HAT integration (X728, X1200)."""

DOMAIN = "geekworm_ups"
MANUFACTURER = "Geekworm"

# REST endpoint exposed by the Geekworm UPS HAT add-on daemon
API_PATH = "/api/ups"

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8099
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Sensor keys returned by the daemon API
KEY_VOLTAGE = "voltage"
KEY_CAPACITY = "capacity"
KEY_AC_PRESENT = "ac_present"
KEY_BATTERY_LOW = "battery_low"
KEY_CHARGING = "charging"
KEY_HW_VERSION = "hw_version"
KEY_BOARD = "board"
