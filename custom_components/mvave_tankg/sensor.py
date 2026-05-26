"""RSSI sensor for the Tank-G."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TankGRssi(entry.runtime_data)])


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
