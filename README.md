# ha-geekworm-ups - Geekworm UPS HATs (X728, X1200) for Home Assistant OS

[![GitHub release](https://img.shields.io/github/v/release/fir006c/geekworm-ups-hat)](https://github.com/fir006c/geekworm-ups-hat/releases/latest)
[![GitHub license](https://img.shields.io/github/license/fir006c/geekworm-ups-hat)](https://github.com/fir006c/geekworm-ups-hat/blob/main/LICENSE)
[![Home Assistant installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=HA%20installs&suffix=%20users&cacheSeconds=14400&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.geekworm_ups.total)](https://github.com/fir006c/geekworm-ups-hat)
[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

> **Note:** this project is based on the original work of [iu1jvo](https://github.com/iu1jvo):
> [iu1jvo/ha-x728](https://github.com/iu1jvo/ha-x728), the Home Assistant app and integration for the
> Geekworm X728. This fork adds the X1200 and a generic board structure for other Geekworm UPS HATs.


## Index

1. [Introduction](#introduction)
2. [Supported boards](#supported-boards)
3. [Prerequisites](#prerequisites)
4. [Entities created](#entities-created)
5. [Hardware GPIO reference](#hardware-gpio-reference)
6. [App configuration options](#app-configuration-options)
7. [Installation](#installation)
    1. [App](#1---app)
    2. [Custom Integration (Marketplace or HACS)](#2---custom-integration-marketplace-or-hacs)
8. [Migrating from the X728-only version](#migrating-from-the-x728-only-version)
9. [REST API](#rest-api)
10. [Enable Debug Logging](#enable-debug-logging)
11. [Contribute To The Project](#contribute-to-the-project)
    1. [Integration](#integration)
    2. [App](#app)
    3. [Adding another UPS HAT](#adding-another-ups-hat)
12. [Credits](#credits)

## Introduction
Full integration between Geekworm UPS HATs and **Home Assistant OS** (HAOS).

Consists of two parts that work together:

| Part | What it does |
|---|---|
| **HA App** (`ha-addon-geekworm/`) | Runs a Python daemon inside a Docker container with access to I2C and GPIO. Reads the hardware and exposes a local REST API. Handles safe shutdown. |
| **Custom Integration** (`custom_components/geekworm_ups/`) | Pure HA integration that polls the daemon REST API and creates entities. Installable via the Home Assistant Marketplace (2026.11+) or HACS (2026.10 and older). |

## Supported boards

| Board | `board` option | Raspberry Pi | Notes |
|---|---|---|---|
| [Geekworm X728](https://wiki.geekworm.com/X728) v1.x .. v2.5 | `x728` | 3 / 4 / 5 | Buzzer, BOOT and power-cut pins supported. Select the revision with `hw_version`. |
| [Geekworm X1200](https://wiki.geekworm.com/X1200) (also sold by Suptronics) | `x1200` | 5 only | No buzzer and no power-cut pin: the Pi 5 cuts power by itself after shutdown. |

Both boards use the MAX17040 fuel gauge (I2C address `0x36`) to read battery voltage and capacity.

## Prerequisites

In order to use the HA Geekworm UPS HAT App, is required the acces to the I2C bus but the I2C bus is not enabled as default.
To enable the I2C bus on HAOS, [follow this istructions](https://www.home-assistant.io/common-tasks/os#enable-i2c).

## Entities created

The entity ids are built from the device name, which contains the board, e.g. `Geekworm X1200 UPS HAT`:

| Entity (X1200 example) | Type | Description |
|---|---|---|
| `sensor.geekworm_x1200_ups_hat_battery_voltage` | Sensor | Battery voltage in Volts |
| `sensor.geekworm_x1200_ups_hat_battery_level` | Sensor | Battery charge in % |
| `sensor.geekworm_x1200_ups_hat_hardware_version` | Sensor (diagnostic) | Detected HW version string |
| `binary_sensor.geekworm_x1200_ups_hat_ac_power` | Binary sensor | ON = AC power present |
| `binary_sensor.geekworm_x1200_ups_hat_battery_low` | Binary sensor | ON = below shutdown threshold |
| `binary_sensor.geekworm_x1200_ups_hat_charging` | Binary sensor | ON = currently charging |

For the X728 the prefix is `geekworm_x728_ups_hat_`.

---

## Hardware GPIO reference

### X728

| GPIO | Direction | Function |
|---|---|---|
| 6 | IN | PLD - Power Loss Detection (HIGH = AC lost) |
| 12 | OUT | BOOT - held HIGH while system is running |
| 13 | OUT | Shutdown trigger (**v1.x / v2.0** only) |
| 20 | OUT | Buzzer |
| 26 | OUT | Shutdown trigger (**v2.1 / v2.2 / v2.3 / v2.4 / v2.5**) |

### X1200

| GPIO | Direction | Function |
|---|---|---|
| 6 | IN | PLD - Power Loss Detection (HIGH = AC OK, inverted compared to the X728) |
| 16 | - | Charge on/off control (not used by the daemon) |

---

## App configuration options

| Option | Default | Description |
|---|---|---|
| `board` | `x728` | UPS HAT model: `x728` or `x1200` |
| `hw_version` | `v2.1` | **X728 only.** Hardware version, selects the shutdown GPIO pin (13 for v1.x/v2.0, 26 for v2.1+ up to v2.5) |
| `daemon_port` | `8099` | TCP port the REST API listens on |
| `poll_interval` | `10` | How often to read hardware (seconds) |
| `shutdown_voltage` | `3.00` | Shutdown if battery voltage < this value (V). Set `0` to disable. |
| `shutdown_capacity` | `5` | Shutdown if battery capacity < this value (%). Set `0` to disable. |
| `shutdown_delay` | `10` | Seconds between HA shutdown command and UPS HAT power-off (power-off pulse is X728 only) |
| `buzzer_on_ac_loss` | `true` | **X728 only.** Beep the buzzer when AC power is lost |
| `gpio_chip` | `autodetect` | GPIO chip device. `autodetect` finds the Raspberry Pi GPIO controller (Pi 3/4/5) |

The `board` option is passed to the daemon as the `UPS_HAT_BOARD` environment variable.

---

## Installation

### 1 - App

1. In HA go to **Settings -> Apps -> Install App -> ... -> Repositories**
2. Add: `https://github.com/fir006c/geekworm-ups-hat`
3. Install **Geekworm UPS HAT Daemon** and start it
4. Configure options (especially `board`, and `hw_version` for the X728)

### 2 - Custom Integration (Marketplace or HACS)

Since Home Assistant 2026.11, HACS is built in as the **Marketplace**, and standalone HACS can no
longer be installed. Use the steps that match your Home Assistant version.

#### Home Assistant 2026.11 and newer (Marketplace)

1. Go to **Settings -> Marketplace**
2. In the upper-right corner, select **Add from link**
3. Enter `fir006c/geekworm-ups-hat` (or `https://github.com/fir006c/geekworm-ups-hat`) and select **Add**.
   Adding a custom repository needs a GitHub account connected to the Marketplace.
4. Install **Geekworm UPS HAT** and restart Home Assistant if asked

#### Home Assistant 2026.10 and older (HACS)

1. In HACS go to **Integrations -> ... -> Custom repositories**
2. Add: `https://github.com/fir006c/geekworm-ups-hat` - category **Integration**
3. Install **Geekworm UPS HAT** and restart Home Assistant

#### Set up the integration

1. Go to **Settings -> Integrations -> Add Integration -> Geekworm UPS HAT**
2. Host: `localhost`, Port: `8099` (or whatever you configured)

---

## Migrating from the X728-only version

This version renames the app (`x728-daemon` -> `geekworm-daemon`), the integration domain
(`x728` -> `geekworm_ups`) and the REST endpoint (`/api/x728` -> `/api/ups`).
There is no automatic migration:

1. Remove the old **X728** integration and the old **Geekworm X728 UPS Daemon** app.
2. Install the new app and integration as described in [Installation](#installation).
3. Update automations and dashboards to the new entity ids.

---

## REST API

The daemon exposes a single endpoint:

```
GET http://localhost:8099/api/ups
```

Response example:
```json
{
  "voltage": 4.05,
  "capacity": 87,
  "ac_present": true,
  "battery_low": false,
  "charging": false,
  "board": "x1200",
  "hw_version": "X1200",
  "shutdown_triggered": false,
  "error": null
}
```

## Enable Debug Logging

If logs are needed for debugging or reporting an issue, use the following configuration.yaml:

```yaml
logger:
  default: error
  logs:
    custom_components.geekworm_ups: debug
```

## Contribute To The Project

### Integration

1. Fork and clone the repository.
2. Open in VSCode and choose to open in devcontainer. Must have VSCode devcontainer prerequisites.
3. Run the command container start from VSCode terminal
4. A fresh Home Assistant test instance will install and will eventually be running on port 9125 with this integration running
5. When the container is running, go to http://localhost:9125 and add Geekworm UPS HAT from the Integration Page.

### App
1. Fork and clone the repository.
2. Open in VSCode. To test the app, there are two way:
    1. Chose to open in a dev container, the integation will start and run in simulation mode.
    2. run the app script in a terminal:
        ```bash
        cd ha-addon-geekworm
        UPS_HAT_BOARD=x1200 SHUTDOWN_VOLTAGE=3.5 SHUTDOWN_CAPACITY=10 DAEMON_PORT=8099 python3 geekworm_daemon.py
        ```
3. Test the exposed API REST in an another terminal window:
    ```bash
    curl -s http://localhost:8099/api/ups | python3 -m json.tool
    ```
    or opening `http://localhost:<DAEMON_PORT>/api/ups` in a browser.

### Adding another UPS HAT

All board specific details live in `ha-addon-geekworm/geekworm_daemon.py`:

1. Write a `_build_<board>()` function returning a `BoardProfile` (PLD pin and the level that
   means "AC OK", optional buzzer / BOOT / shutdown pins; use `None` for missing pins).
2. Register it in `BOARD_BUILDERS`.
3. Add the board name to the `board` schema in `ha-addon-geekworm/config.yaml`.
4. Document the board in this README.

The integration needs no changes: it shows the board reported by the daemon.

## Credits

This project is a fork of [iu1jvo/ha-x728](https://github.com/iu1jvo/ha-x728) by
[iu1jvo](https://github.com/iu1jvo), the original Home Assistant app and integration for the Geekworm X728.

That project is based on the original shell scripts and Python utilities by [iu1jvo](https://github.com/iu1jvo/x728),
which were in turn derived from the official [geekworm-com/x728](https://github.com/geekworm-com/x728) scripts.
X1200 support is based on [geekworm-com/x120x](https://github.com/geekworm-com/x120x) and
[suptronics/x120x](https://github.com/suptronics/x120x).
