"""Coordinator: tracks presence/RSSI via advertisements, switches presets via BLE."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from mvave_tankg_ble import TankG

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_POLL_INTERVAL = timedelta(minutes=5)


class TankGCoordinator(DataUpdateCoordinator[dict]):
    """Holds device presence/RSSI and switches presets over BLE."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=_POLL_INTERVAL)
        self.address: str = entry.unique_id or entry.data[CONF_ADDRESS]
        self._entry = entry
        self.present: bool = False
        self.rssi: int | None = None
        self._unsub_bt = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self.address)},
            identifiers={(DOMAIN, self.address)},
            manufacturer="M-Vave",
            model="Tank-G",
            name="M-Vave Tank-G",
        )

    async def async_start(self) -> None:
        """Register the advertisement callback and do a first refresh."""
        self._unsub_bt = bluetooth.async_register_callback(
            self.hass,
            self._on_advertisement,
            {"address": self.address, "connectable": False},
            BluetoothScanningMode.ACTIVE,
        )
        self.present = bluetooth.async_address_present(
            self.hass, self.address, connectable=False
        )
        await self.async_config_entry_first_refresh()

    async def async_stop(self) -> None:
        if self._unsub_bt is not None:
            self._unsub_bt()
            self._unsub_bt = None

    @callback
    def _on_advertisement(
        self, info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        self.present = True
        self.rssi = info.rssi
        self.async_update_listeners()

    async def _async_update_data(self) -> dict:
        """Refresh presence from the bluetooth manager (RSSI comes via callback)."""
        self.present = bluetooth.async_address_present(
            self.hass, self.address, connectable=False
        )
        return {}

    async def async_set_preset(self, preset: int) -> None:
        """Switch the pedal to UI preset 1-36 over BLE-MIDI."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed("dispositivo não conectável no momento")
        async with TankG(ble_device) as pedal:
            await pedal.set_preset(preset)
