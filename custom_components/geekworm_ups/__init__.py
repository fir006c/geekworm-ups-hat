"""Geekworm UPS HAT integration (X728, X1200) for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_PATH,
    DOMAIN,
    KEY_BOARD,
    KEY_HW_VERSION,
    MANUFACTURER,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Geekworm UPS HAT from a config entry."""
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = UpsDataCoordinator(hass, host, port, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def board_name(data: dict | None) -> str:
    """Return the board name reported by the daemon, e.g. "X1200"."""
    board = (data or {}).get(KEY_BOARD)
    return board.upper() if board else ""


def ups_hat_name(data: dict | None) -> str:
    """Return the display name, e.g. "Geekworm X1200 UPS HAT"."""
    return " ".join(filter(None, [MANUFACTURER, board_name(data), "UPS HAT"]))


def device_info(coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> DeviceInfo:
    """Device info shared by all entities of a config entry."""
    data = coordinator.data or {}
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=ups_hat_name(data),
        manufacturer=MANUFACTURER,
        model=data.get(KEY_HW_VERSION) or board_name(data) or None,
    )


class UpsDataCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from the Geekworm UPS HAT daemon."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, scan_interval: int):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.port = port
        self._url = f"http://{host}:{port}{API_PATH}"

    async def _async_update_data(self) -> dict:
        """Fetch data from the Geekworm UPS HAT daemon REST API."""
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self._url) as response:
                        if response.status != 200:
                            raise UpdateFailed(
                                f"UPS HAT daemon returned HTTP {response.status}"
                            )
                        return await response.json()
        except aiohttp.ClientConnectorError as err:
            raise UpdateFailed(
                f"Cannot connect to UPS HAT daemon at {self._url}: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching UPS HAT data: {err}") from err
