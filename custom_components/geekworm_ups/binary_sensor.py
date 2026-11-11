"""Binary sensor platform for Geekworm UPS HATs."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UpsDataCoordinator, device_info
from .const import (
    DOMAIN,
    KEY_AC_PRESENT,
    KEY_BATTERY_LOW,
    KEY_CHARGING,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UPS HAT binary sensors."""
    coordinator: UpsDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UpsAcPresentSensor(coordinator, entry),
            UpsBatteryLowSensor(coordinator, entry),
            UpsChargingSensor(coordinator, entry),
        ]
    )


class UpsBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base binary sensor."""

    _attr_has_entity_name = True

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        coordinator: UpsDataCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = device_info(coordinator, entry)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._key in (
            self.coordinator.data or {}
        )


class UpsAcPresentSensor(UpsBaseBinarySensor):
    """AC power present sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, KEY_AC_PRESENT, "AC Power", "ac_present"
        )
        self._attr_device_class = BinarySensorDeviceClass.PLUG
        self._attr_icon = "mdi:power-plug"


class UpsBatteryLowSensor(UpsBaseBinarySensor):
    """Battery low alert sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, KEY_BATTERY_LOW, "Battery Low", "battery_low"
        )
        self._attr_device_class = BinarySensorDeviceClass.BATTERY
        self._attr_icon = "mdi:battery-alert"


class UpsChargingSensor(UpsBaseBinarySensor):
    """Battery charging sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, KEY_CHARGING, "Charging", "charging"
        )
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
        self._attr_icon = "mdi:battery-charging"
