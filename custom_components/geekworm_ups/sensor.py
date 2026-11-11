"""Sensor platform for Geekworm UPS HATs."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    EntityCategory,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UpsDataCoordinator, device_info
from .const import DOMAIN, KEY_VOLTAGE, KEY_CAPACITY, KEY_HW_VERSION


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UPS HAT sensors."""
    coordinator: UpsDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UpsVoltageSensor(coordinator, entry),
            UpsCapacitySensor(coordinator, entry),
            UpsHwVersionSensor(coordinator, entry),
        ]
    )


class UpsBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for UPS HAT sensors."""

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
    def native_value(self):
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._key in (
            self.coordinator.data or {}
        )


class UpsVoltageSensor(UpsBaseSensor):
    """Battery voltage sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, KEY_VOLTAGE, "Battery Voltage", "voltage"
        )
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_suggested_display_precision = 2
        self._attr_icon = "mdi:current-dc"


class UpsCapacitySensor(UpsBaseSensor):
    """Battery capacity (%) sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, KEY_CAPACITY, "Battery Level", "capacity"
        )
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_suggested_display_precision = 0
        self._attr_icon = "mdi:battery"


class UpsHwVersionSensor(UpsBaseSensor):
    """Hardware version info sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, KEY_HW_VERSION, "Hardware Version", "hw_version"
        )
        self._attr_icon = "mdi:chip"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
