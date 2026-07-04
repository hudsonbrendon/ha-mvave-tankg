"""The M-Vave Tank-G integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TankGCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.NUMBER,
]

type TankGConfigEntry = ConfigEntry[TankGCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TankGConfigEntry) -> bool:
    coordinator = TankGCoordinator(hass, entry)
    # Release the BT advertisement callback registered by async_start even
    # when setup fails afterwards (e.g. ConfigEntryNotReady from the first
    # refresh); otherwise every setup retry leaks a callback registration.
    entry.async_on_unload(coordinator.async_stop)
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TankGConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
