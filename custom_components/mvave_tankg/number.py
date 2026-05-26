"""Preset selector (number) for the Tank-G via BLE-MIDI Program Change."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from mvave_tankg_ble.const import PRESET_COUNT, PRESET_MIN

from . import TankGConfigEntry
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TankGPreset(entry.runtime_data)])


class TankGPreset(CoordinatorEntity[TankGCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Preset"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_min_value = PRESET_MIN
    _attr_native_max_value = PRESET_COUNT

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_preset"
        self._attr_device_info = coordinator.device_info
        self._current: int | None = None

    @property
    def native_value(self) -> int | None:
        # BLE-MIDI Program Change is one-way; reflect the last value we sent.
        return self._current

    async def async_set_native_value(self, value: float) -> None:
        preset = int(value)
        await self.coordinator.async_set_preset(preset)
        self._current = preset
        self.async_write_ha_state()
