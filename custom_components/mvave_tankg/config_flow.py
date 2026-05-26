"""Config flow for M-Vave Tank-G."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from mvave_tankg_ble.const import MIDI_SERVICE_UUID

from .const import DOMAIN

_DEFAULT_NAME = "M-Vave Tank-G"


def _is_tankg(info: BluetoothServiceInfoBleak) -> bool:
    """A Tank-G advertises the BLE-MIDI service; the name may be absent on
    passive scanners, so match on the service UUID too."""
    if info.name and info.name.upper().startswith("TANK-G"):
        return True
    return MIDI_SERVICE_UUID in (info.service_uuids or [])


class TankGConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery and setup of a Tank-G."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or _DEFAULT_NAME
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        name = self._discovery.name or _DEFAULT_NAME
        if user_input is not None:
            return self.async_create_entry(title=name, data={})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered.get(address, address), data={}
            )

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=False):
            if info.address in current:
                continue
            if _is_tankg(info):
                self._discovered[info.address] = info.name or _DEFAULT_NAME

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )
