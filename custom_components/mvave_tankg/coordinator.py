"""Coordinator: tracks presence via advertisements, polls battery via connection."""
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

from .ble_midi import program_change_frame
from .const import (
    BATTERY_LEVEL_CHAR_UUID,
    DOMAIN,
    HAS_STANDARD_BATTERY,
    MIDI_IO_CHAR_UUID,
)

_LOGGER = logging.getLogger(__name__)
_POLL_INTERVAL = timedelta(minutes=5)


class TankGCoordinator(DataUpdateCoordinator[dict]):
    """Holds device state and BLE access."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=_POLL_INTERVAL
        )
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
        """Refresh presence; read battery if supported by recon findings."""
        self.present = bluetooth.async_address_present(
            self.hass, self.address, connectable=False
        )
        data: dict = {"battery": self.data.get("battery") if self.data else None}
        if HAS_STANDARD_BATTERY and self.present:
            data["battery"] = await self._read_battery()
        return data

    async def _read_battery(self) -> int | None:
        from bleak_retry_connector import (
            BleakClientWithServiceCache,
            establish_connection,
        )

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed("dispositivo não conectável no momento")
        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self.address
        )
        try:
            raw = await client.read_gatt_char(BATTERY_LEVEL_CHAR_UUID)
            return int(raw[0])
        finally:
            await client.disconnect()

    async def async_send_program_change(self, program: int) -> None:
        """Send a BLE-MIDI Program Change to switch preset."""
        from bleak_retry_connector import (
            BleakClientWithServiceCache,
            establish_connection,
        )

        from .const import MIDI_CHANNEL

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed("dispositivo não conectável no momento")
        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self.address
        )
        try:
            await client.write_gatt_char(
                MIDI_IO_CHAR_UUID,
                program_change_frame(program, MIDI_CHANNEL),
                response=False,
            )
        finally:
            await client.disconnect()
