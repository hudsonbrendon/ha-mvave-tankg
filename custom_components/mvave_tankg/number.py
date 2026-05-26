"""Preset selector (number) for the Tank-G via BLE-MIDI Program Change."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .const import PRESET_COUNT, PRESET_UI_OFFSET
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
    _attr_native_min_value = 1

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_preset"
        self._attr_device_info = coordinator.device_info
        self._attr_native_max_value = PRESET_COUNT
        self._current: int | None = None

    @property
    def native_value(self) -> int | None:
        # BLE-MIDI Program Change é one-way; refletimos o último valor enviado.
        return self._current

    async def async_set_native_value(self, value: float) -> None:
        ui_preset = int(value)
        program = ui_preset - PRESET_UI_OFFSET
        await self.coordinator.async_send_program_change(program)
        self._current = ui_preset
        self.async_write_ha_state()
