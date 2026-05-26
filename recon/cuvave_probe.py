"""Probe the Tank-G with known Cuvave/M-Vave SysEx *query* commands.

Goal: find out whether the pedal answers device-state queries (candidate
battery / settings) and on which transport — the vendor characteristic
(0xAE41 write / 0xAE42 notify) or the standard BLE-MIDI characteristic.

Only QUERY commands are sent (discovery 0x45, settings 0x0D41), taken verbatim
from the M-Vave Chocolate reverse-engineering project (they carry their own
checksums and should not change device configuration).

Resilient: detects disconnects and reconnects per command; first listens
without sending, in case the pedal pushes state/heartbeat on its own.

Usage: python recon/cuvave_probe.py [ADDRESS]
"""
import asyncio
import sys
import time

from bleak import BleakClient, BleakScanner

MIDI_SERVICE = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
MIDI_IO = "7772e5db-3868-4112-a1a9-f2669d106bf3"
VENDOR_WRITE = "0000ae41-0000-1000-8000-00805f9b34fb"
VENDOR_NOTIFY = "0000ae42-0000-1000-8000-00805f9b34fb"

COMMANDS = [
    ("midi identity req", bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])),
    ("discovery 0x45", bytes([0xF0, 0x00, 0x32, 0x45, 0x00, 0x00, 0x00, 0x40, 0x7F, 0xF7])),
    ("settings 0x0D41", bytes([0xF0, 0x00, 0x32, 0x0D, 0x41, 0x00, 0x00, 0x00, 0x02,
                                0x00, 0x00, 0x00, 0x00, 0x10, 0x7E, 0x00, 0x00, 0x07,
                                0x00, 0xF7])),
]


def ble_midi_sysex(payload: bytes) -> bytes:
    """Wrap a full SysEx (F0..F7) in a single-packet BLE-MIDI frame."""
    return bytes([0x80, 0x80]) + payload[:-1] + bytes([0x80]) + payload[-1:]


def _ascii(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def _handler(label: str, sink: list):
    def h(_char, data: bytearray) -> None:
        b = bytes(data)
        print(f"  [{time.strftime('%H:%M:%S')}] NOTIFY {label}: {b.hex(' ')}  | {_ascii(b)}")
        sink.append((label, b))
    return h


async def find_address() -> str | None:
    print("Scanning 12s para achar o Tank-G...")
    devs = await BleakScanner.discover(timeout=12.0, return_adv=True)
    for dev, adv in devs.values():
        name = dev.name or adv.local_name or ""
        svcs = [s.lower() for s in adv.service_uuids]
        if "tank" in name.lower() or MIDI_SERVICE in svcs:
            print(f"  achei: {dev.address}  name={name!r}  rssi={adv.rssi}")
            return dev.address
    return None


async def connect(address: str, sink: list) -> BleakClient:
    def on_disc(_c):
        print(f"  ! [{time.strftime('%H:%M:%S')}] desconectou")
    client = BleakClient(address, disconnected_callback=on_disc)
    await client.connect()
    await client.start_notify(MIDI_IO, _handler("midi", sink))
    try:
        await client.start_notify(VENDOR_NOTIFY, _handler("ae42(vendor)", sink))
    except Exception as exc:  # noqa: BLE001
        print(f"  ae42 notify falhou: {exc!r}")
    return client


async def main(address: str | None) -> None:
    if not address:
        address = await find_address()
        if not address:
            print("Tank-G não encontrado. Liga o pedal, B+C 3s (BT piscando), perto do Mac.")
            return

    sink: list = []
    print(f"Conectando em {address} ...")
    client = await connect(address, sink)
    print(f"Conectado: {client.is_connected}")

    print("Escutando 6s SEM enviar (heartbeat/estado espontâneo?)...")
    await asyncio.sleep(6.0)
    print(f"  espontâneos: {len(sink)}")

    for label, payload in COMMANDS:
        for transport in ("ae41", "midi"):
            if not client.is_connected:
                print("  reconectando...")
                try:
                    client = await connect(address, sink)
                except Exception as exc:  # noqa: BLE001
                    print(f"  reconnect falhou: {exc!r}")
                    break
                await asyncio.sleep(1.0)
            char = VENDOR_WRITE if transport == "ae41" else MIDI_IO
            data = payload if transport == "ae41" else ble_midi_sysex(payload)
            n0 = len(sink)
            print(f"\n>> {label} -> {transport}: {data.hex(' ')}")
            try:
                await client.write_gatt_char(char, data, response=False)
            except Exception as exc:  # noqa: BLE001
                print(f"   erro {transport}: {exc!r}")
                continue
            await asyncio.sleep(2.5)
            print(f"   respostas novas: {len(sink) - n0}")

    await asyncio.sleep(2.0)
    try:
        if client.is_connected:
            await client.disconnect()
    except Exception:  # noqa: BLE001
        pass
    print(f"\nTOTAL notifies capturados: {len(sink)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
