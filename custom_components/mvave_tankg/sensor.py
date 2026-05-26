"""RSSI and battery sensors for the Tank-G."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .const import HAS_STANDARD_BATTERY
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[CoordinatorEntity] = [TankGRssi(coordinator)]
    if HAS_STANDARD_BATTERY:
        entities.append(TankGBattery(coordinator))
    async_add_entities(entities)


class TankGRssi(CoordinatorEntity[TankGCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sinal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_rssi"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.rssi


class TankGBattery(CoordinatorEntity[TankGCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Bateria"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_battery"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("battery")
