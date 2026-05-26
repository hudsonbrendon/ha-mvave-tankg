from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.data_entry_flow import FlowResultType

from mvave_tankg_ble.const import MIDI_SERVICE_UUID

from custom_components.mvave_tankg.config_flow import _is_tankg
from custom_components.mvave_tankg.const import DOMAIN


def _info(name="", uuids=None):
    return BluetoothServiceInfoBleak(
        name=name,
        address="AA:BB:CC:DD:EE:FF",
        rssi=-55,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids or [],
        source="local",
        device=None,
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=-127,
    )


def test_is_tankg_by_name():
    assert _is_tankg(_info(name="TANK-Gv2_BLE"))


def test_is_tankg_by_service_uuid_without_name():
    # passive scanners may not capture the name — match on the BLE-MIDI service.
    assert _is_tankg(_info(name="", uuids=[MIDI_SERVICE_UUID]))


def test_is_tankg_rejects_other_device():
    assert not _is_tankg(
        _info(name="SomeLight", uuids=["0000180f-0000-1000-8000-00805f9b34fb"])
    )

SERVICE_INFO = BluetoothServiceInfoBleak(
    name="TANK-Gv2_BLE",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-55,
    manufacturer_data={},
    service_data={},
    service_uuids=["03b80e5a-ede8-4b33-a751-6ce34ec4c700"],
    source="local",
    device=None,
    advertisement=None,
    connectable=True,
    time=0,
    tx_power=-127,
)


async def test_bluetooth_discovery_creates_entry(hass):
    # Patch setup so the flow test stays isolated from real BLE/coordinator setup.
    with patch(
        "custom_components.mvave_tankg.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=SERVICE_INFO
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TANK-Gv2_BLE"
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"
