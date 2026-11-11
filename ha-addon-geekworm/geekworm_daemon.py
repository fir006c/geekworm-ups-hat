#!/usr/bin/env python3
"""
Geekworm UPS HAT Daemon for Home Assistant OS Add-on.

Supported boards (selected with the UPS_HAT_BOARD environment variable):
  x728  - Geekworm X728 (v1.x .. v2.5)
  x1200 - Geekworm / Suptronics X1200 (Raspberry Pi 5 only)

Both boards read battery voltage/capacity via I2C (MAX17040 @ 0x36) and
AC power loss via GPIO6 (PLD pin). The daemon exposes a REST API on
http://0.0.0.0:<PORT>/api/ups and handles safe shutdown when the battery
falls below the configured threshold voltage or capacity.

Hardware GPIO map:
  X728:
    GPIO6  -> PLD  (Power Loss Detection, LOW=AC OK, HIGH=AC Lost)
    GPIO20 -> Buzzer
    GPIO26 -> Software shutdown trigger (v2.1+)
    GPIO13 -> Software shutdown trigger (v1.x / v2.0)
    GPIO12 -> BOOT signal (output, kept HIGH while running)
  X1200:
    GPIO6  -> PLD  (Power Loss Detection, HIGH=AC OK, LOW=AC Lost)
    (no buzzer, no BOOT, no shutdown pin: the Pi 5 cuts power on halt)

To support another HAT, add a builder to BOARD_BUILDERS and the board
name to the add-on config.yaml schema.
"""

import json
import logging
import os
import struct
import subprocess
import time
import threading
import pwd
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Read configuration from environment variables (set by the add-on config)
# ---------------------------------------------------------------------------
BOARD = os.environ.get("UPS_HAT_BOARD", "x728")      # supported values: x728, x1200
HW_VERSION = os.environ.get("HW_VERSION", "v2.1")   # X728 only: v1, v2.0, v2.1+
PORT = int(os.environ.get("DAEMON_PORT", "8099"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))   # seconds

# Shutdown thresholds (0 = disabled)
SHUTDOWN_VOLTAGE = float(os.environ.get("SHUTDOWN_VOLTAGE", "3.00"))  # Volts
SHUTDOWN_CAPACITY = int(os.environ.get("SHUTDOWN_CAPACITY", "5"))       # %
SHUTDOWN_DELAY = int(os.environ.get("SHUTDOWN_DELAY", "10"))         # seconds

BUZZER_ON_AC_LOSS = os.environ.get("BUZZER_ON_AC_LOSS", "true").lower() == "true"
# "autodetect" or specific path like "/dev/gpiochip0"
GPIO_CHIP = os.environ.get("GPIO_CHIP", "autodetect")

CHIP_FALLBACK = "/dev/gpiochip0"  # used if autodetect fails

API_PATH = "/api/ups"

# MAX17040 fuel gauge, shared by all supported boards
I2C_ADDR = 0x36
I2C_BUS = 1

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [geekworm-daemon] %(levelname)s: %(message)s",
)
log = logging.getLogger("geekworm-daemon")


# ---------------------------------------------------------------------------
# Board profiles
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BoardProfile:
    """GPIO layout of a UPS HAT. A pin set to None is not present."""

    board: str                  # board id, e.g. "x728"
    label: str                  # human readable model, e.g. "X728 v2.1+"
    pld_pin: int                # Power Loss Detection input
    pld_ac_ok_level: int        # PLD level (0/1) that means "AC present"
    buzzer_pin: int | None = None
    boot_pin: int | None = None
    shutdown_pin: int | None = None


def normalize_hw_version(hw_version: str) -> str:
    """Normalize X728 hardware version strings to the groups we actually support."""
    value = (hw_version or "").strip().lower().replace(" ", "")
    aliases = {
        "v1": "v1",
        "v1.x": "v1",
        "v1.x/v2.0": "v1",
        "v2.0": "v2.0",
        "v2.1": "v2.1+",
        "v2.1+": "v2.1+",
    }
    if value in aliases:
        return aliases[value]
    return "v2.1+"


def _build_x728(hw_version: str) -> BoardProfile:
    """X728: PLD HIGH = AC lost, shutdown pin depends on the revision."""
    group = normalize_hw_version(hw_version)
    if group == "v1":
        shutdown_pin, label = 13, "X728 v1"
    elif group == "v2.0":
        shutdown_pin, label = 13, "X728 v2.0"
    else:
        shutdown_pin, label = 26, "X728 v2.1+"
    return BoardProfile(
        board="x728",
        label=label,
        pld_pin=6,
        pld_ac_ok_level=0,
        buzzer_pin=20,
        boot_pin=12,
        shutdown_pin=shutdown_pin,
    )


def _build_x1200(_hw_version: str) -> BoardProfile:
    """X1200: PLD HIGH = AC OK, no buzzer / boot / shutdown pins."""
    return BoardProfile(board="x1200", label="X1200", pld_pin=6, pld_ac_ok_level=1)


BOARD_BUILDERS = {
    "x728": _build_x728,
    "x1200": _build_x1200,
}


def build_profile(board: str, hw_version: str) -> BoardProfile:
    """Return the profile for the given board, falling back to the X728."""
    key = (board or "").strip().lower()
    builder = BOARD_BUILDERS.get(key)
    if builder is None:
        log.warning("Unknown board '%s', falling back to x728", board)
        builder = _build_x728
    return builder(hw_version)


PROFILE = build_profile(BOARD, HW_VERSION)

# ---------------------------------------------------------------------------
# Global Hardware State & Graceful Imports
# ---------------------------------------------------------------------------
GPIO_AVAILABLE = False  # pylint: disable=invalid-name
I2C_AVAILABLE = False  # pylint: disable=invalid-name

try:
    import gpiod
    GPIO_AVAILABLE = True  # pylint: disable=invalid-name
except (ImportError, RuntimeError) as err:
    log.warning("gpiod not available – GPIO running in SIMULATION mode (%s)", err)

try:
    import smbus2
    I2C_AVAILABLE = True  # pylint: disable=invalid-name
except (ImportError, RuntimeError) as err:
    log.warning("smbus2 not available – I2C running in SIMULATION mode (%s)", err)

# ---------------------------------------------------------------------------
# Shared state (written by the monitor thread, read by the HTTP thread)
# ---------------------------------------------------------------------------
state_lock = threading.Lock()
current_state: dict = {
    "voltage": None,
    "capacity": None,
    "ac_present": None,
    "battery_low": False,
    "charging": False,
    "board": PROFILE.board,
    "hw_version": PROFILE.label,
    "shutdown_triggered": False,
    "error": None,
}


# ---------------------------------------------------------------------------
# Hardware helpers
# ---------------------------------------------------------------------------
# Known GPIO controller names per platform
_KNOWN_CONTROLLERS = [
    "pinctrl-rp1",      # Raspberry Pi 5
    "pinctrl-bcm2711",  # Raspberry Pi 4
    "pinctrl-bcm2835",  # Raspberry Pi 3 / Zero
]

# gpiod v2 request handle (set in gpio_setup, used in gpio_read/write)
_gpio_request = None  # pylint: disable=invalid-name


def find_gpio_chip() -> str:
    """Auto-detect the correct gpiochip by controller name (gpiod v2 API).

    Scans /dev/gpiochip* and matches against known RPi controller labels.
    Falls back to GPIO_CHIP env var if detection fails.
    """
    for i in range(5):
        path = f"/dev/gpiochip{i}"
        if not os.path.exists(path):
            continue
        try:
            with gpiod.Chip(path) as chip:
                label = chip.get_info().label
                for controller in _KNOWN_CONTROLLERS:
                    if controller in label:
                        log.info("Auto-detected GPIO chip: %s (label: %s)", path, label)
                        return path
        except Exception:  # pylint: disable=broad-except
            continue
    log.warning("GPIO chip auto-detection failed, using fallback: %s", CHIP_FALLBACK)
    return CHIP_FALLBACK


def gpio_setup():
    """Initialise GPIO pins via gpiod v2 API."""
    global _gpio_request  # pylint: disable=global-statement

    chip_path = find_gpio_chip() if GPIO_CHIP == "autodetect" else GPIO_CHIP

    # PLD is always an INPUT; optional output pins are added when the board has them
    line_config = {
        PROFILE.pld_pin: gpiod.LineSettings(direction=gpiod.line.Direction.INPUT),
    }
    outputs = (
        (PROFILE.buzzer_pin, gpiod.line.Value.INACTIVE),
        (PROFILE.boot_pin, gpiod.line.Value.ACTIVE),        # HIGH = system is up
        (PROFILE.shutdown_pin, gpiod.line.Value.INACTIVE),
    )
    for pin, initial in outputs:
        if pin is not None:
            line_config[pin] = gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=initial,
            )

    _gpio_request = gpiod.request_lines(
        chip_path,
        consumer="geekworm-daemon",
        config=line_config,
    )

    log.info(
        "GPIO configured via gpiod v2 (%s) for %s. Pins: %s",
        chip_path, PROFILE.label, sorted(line_config),
    )


def gpio_read(pin: int) -> int:
    """Read the current value of a GPIO pin (1=high, 0=low)."""
    if _gpio_request is None:
        return 0
    val = _gpio_request.get_value(pin)
    return 1 if val == gpiod.line.Value.ACTIVE else 0


def gpio_write(pin: int | None, value: int) -> None:
    """Write a value to a GPIO pin (1=high, 0=low). No-op for a missing pin."""
    if _gpio_request is None or pin is None:
        return
    gpio_val = gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE
    _gpio_request.set_value(pin, gpio_val)


def read_voltage(bus) -> float:
    """Read battery voltage from MAX17040 via I2C."""
    raw = bus.read_word_data(I2C_ADDR, 2)
    swapped = struct.unpack("<H", struct.pack(">H", raw))[0]
    return round(swapped * 1.25 / 1000 / 16, 3)


def read_capacity(bus) -> int:
    """Read battery capacity from MAX17040 via I2C."""
    raw = bus.read_word_data(I2C_ADDR, 4)
    swapped = struct.unpack("<H", struct.pack(">H", raw))[0]
    return int(swapped / 256)


def do_shutdown():
    """Perform a graceful HA shutdown then cut UPS HAT power."""
    log.warning("SHUTDOWN SEQUENCE STARTED")
    # 1. Ask HA OS to shut down gracefully
    try:
        subprocess.run(["ha", "os", "shutdown"], timeout=30, check=False)
    except Exception as e:  # pylint: disable=broad-except
        log.error("Failed to call 'ha os shutdown': %s", e)
    # 2. Wait for OS to settle, then pulse the UPS HAT shutdown pin (if the board has one;
    #    boards without it, like the X1200, cut power when the Pi halts)
    time.sleep(SHUTDOWN_DELAY)
    if GPIO_AVAILABLE and _gpio_request is not None and PROFILE.shutdown_pin is not None:
        gpio_write(PROFILE.shutdown_pin, 1)
        time.sleep(3)
        gpio_write(PROFILE.shutdown_pin, 0)


def buzzer_beep(count: int = 1, on_ms: int = 100, off_ms: int = 100):
    """Sound the buzzer for the given number of pulses."""
    if not GPIO_AVAILABLE or PROFILE.buzzer_pin is None:
        return
    for _ in range(count):
        gpio_write(PROFILE.buzzer_pin, 1)
        time.sleep(on_ms / 1000)
        gpio_write(PROFILE.buzzer_pin, 0)
        time.sleep(off_ms / 1000)


# ---------------------------------------------------------------------------
# Monitor thread
# ---------------------------------------------------------------------------

def monitor_loop():
    """Background thread: poll hardware and update shared state."""
    bus = None
    if GPIO_AVAILABLE:
        try:
            gpio_setup()
        except Exception as e:  # pylint: disable=broad-except
            log.error("GPIO hardware setup failed. Running GPIO in simulation: %s", e)

    if I2C_AVAILABLE:
        try:
            bus = smbus2.SMBus(I2C_BUS)
        except Exception as e:  # pylint: disable=broad-except
            log.error("Cannot open I2C bus: %s", e)

    shutdown_pending = False

    while True:
        try:
            voltage = read_voltage(bus) if bus else None
            capacity = read_capacity(bus) if bus else None
            ac_present = (
                gpio_read(PROFILE.pld_pin) == PROFILE.pld_ac_ok_level
                if GPIO_AVAILABLE and _gpio_request is not None
                else None
            )

            # Derive states
            battery_low = False
            if voltage is not None and SHUTDOWN_VOLTAGE > 0 and voltage < SHUTDOWN_VOLTAGE:
                battery_low = True
            if capacity is not None and SHUTDOWN_CAPACITY > 0 and capacity < SHUTDOWN_CAPACITY:
                battery_low = True

            # Charging: AC present and not full
            charging = bool(ac_present and capacity is not None and capacity < 100)

            with state_lock:
                current_state.update({
                    "voltage":   voltage,
                    "capacity":  capacity,
                    "ac_present": ac_present,
                    "battery_low": battery_low,
                    "charging":  charging,
                    "error":     None,
                })

            # --- AC loss buzzer ---
            if GPIO_AVAILABLE and _gpio_request is not None \
                    and PROFILE.buzzer_pin is not None \
                    and BUZZER_ON_AC_LOSS and ac_present is False:
                buzzer_beep(count=1, on_ms=100, off_ms=100)

            # --- Shutdown logic ---
            if battery_low and not shutdown_pending:
                shutdown_pending = True
                log.warning(
                    "Battery critical (%.2fV / %d%%) – initiating shutdown in %ds",
                    voltage or 0, capacity or 0, SHUTDOWN_DELAY,
                )
                with state_lock:
                    current_state["shutdown_triggered"] = True
                t = threading.Thread(target=do_shutdown, daemon=True)
                t.start()

        except Exception as e:  # pylint: disable=broad-except
            log.error("Monitor error: %s", e)
            with state_lock:
                current_state["error"] = str(e)

        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# HTTP REST API
# ---------------------------------------------------------------------------

class UpsHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler exposing the UPS HAT state on API_PATH."""

    def log_message(self, fmt, *args):  # pylint: disable=arguments-differ
        pass  # suppress per-request access log noise

    def do_GET(self):   # pylint: disable=invalid-name
        """Handle GET requests."""
        if self.path == API_PATH:
            with state_lock:
                payload = json.dumps(current_state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    log.info(
        "Starting Geekworm UPS HAT daemon | board=%s | hw=%s | port=%d | poll=%ds",
        PROFILE.board, PROFILE.label, PORT, POLL_INTERVAL,
    )
    log.info(
        "Shutdown thresholds: voltage<%.2fV OR capacity<%d%% (delay %ds)",
        SHUTDOWN_VOLTAGE, SHUTDOWN_CAPACITY, SHUTDOWN_DELAY,
    )
    log.info("Script executed by: %s (UID: %d)", pwd.getpwuid(os.getuid()).pw_name, os.getuid())

    monitor = threading.Thread(target=monitor_loop, daemon=True, name="ups-monitor")
    monitor.start()

    server = HTTPServer(("0.0.0.0", PORT), UpsHandler)
    log.info("REST API listening on http://0.0.0.0:%d%s", PORT, API_PATH)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Daemon stopped.")
        if GPIO_AVAILABLE and _gpio_request is not None:
            _gpio_request.release()
