"""Presence binary sensor for the Tank-G."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TankGPresence(entry.runtime_data)])


class TankGPresence(CoordinatorEntity[TankGCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Presença"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_presence"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return self.coordinator.present
