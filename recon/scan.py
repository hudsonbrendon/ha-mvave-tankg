"""Scan BLE devices and dump services/characteristics for a chosen address.

Usage:
  python recon/scan.py            # scan and list nearby BLE devices
  python recon/scan.py <ADDRESS>  # connect and enumerate GATT services
"""
import asyncio
import sys

from bleak import BleakClient, BleakScanner


BLE_MIDI_SVC = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"


async def scan() -> None:
    print("Scanning 15s... (ligue o pedal e pressione o footswitch PRESET p/ ativar BT)")
    devices = await BleakScanner.discover(timeout=15.0, return_adv=True)
    if not devices:
        print("Nenhum dispositivo BLE encontrado.")
        return
    rows = sorted(devices.values(), key=lambda da: da[1].rssi, reverse=True)
    for dev, adv in rows:
        name = dev.name or adv.local_name or "?"
        svcs = [s.lower() for s in adv.service_uuids]
        is_midi = BLE_MIDI_SVC in svcs
        flag = ""
        if name and "tank" in name.lower():
            flag = "  <<< POSSÍVEL TANK-G (nome)"
        elif is_midi:
            flag = "  <<< BLE-MIDI (provável Tank-G)"
        mfg = {k: v.hex() for k, v in (adv.manufacturer_data or {}).items()}
        print(f"{dev.address}  rssi={adv.rssi:>4}  name={name!r}  "
              f"svc={adv.service_uuids}  mfg={mfg}{flag}")


async def enumerate_gatt(address: str) -> None:
    print(f"Conectando em {address} ...")
    async with BleakClient(address) as client:
        print(f"Conectado: {client.is_connected}")
        for service in client.services:
            print(f"[service] {service.uuid}  ({service.description})")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"    [char] {char.uuid}  props=[{props}]")
                for desc in char.descriptors:
                    print(f"        [desc] {desc.uuid}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        asyncio.run(enumerate_gatt(sys.argv[1]))
    else:
        asyncio.run(scan())
