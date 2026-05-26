"""Live preset-control test for the Tank-G (no Android needed).

Connects, subscribes to both notify characteristics (vendor 0xAE42 and BLE-MIDI),
reads the readable MIDI char, then sends a sequence of BLE-MIDI Program Change
messages so you can watch the pedal switch presets. Any notification (candidate
battery/preset feedback) is printed with a timestamp.

Usage:
  python recon/preset_test.py <ADDRESS> [channel] [prog1 prog2 ...]
    channel: MIDI channel 0-15 to try (default 0)
    progN:   program numbers to send in order (default 0 8 17 26 0)
"""
import asyncio
import sys
import time

from bleak import BleakClient

VENDOR_NOTIFY = "0000ae42-0000-1000-8000-00805f9b34fb"
MIDI_IO = "7772e5db-3868-4112-a1a9-f2669d106bf3"

# Presets to cycle through so the change is visually obvious on the pedal.
# Tank-G has 36 presets (A1-D9); program N is 0-indexed.
PROGRAMS = [0, 8, 17, 26, 0]


def program_change_frame(program: int, channel: int = 0) -> bytes:
    """BLE-MIDI packet carrying one Program Change (status 0xC0|channel)."""
    header = 0x80
    timestamp = 0x80
    status = 0xC0 | (channel & 0x0F)
    return bytes([header, timestamp, status, program & 0x7F])


def _make_handler(label: str):
    def handler(_char, data: bytearray) -> None:
        print(f"  [{time.strftime('%H:%M:%S')}] NOTIFY {label}: {data.hex()}  ({list(data)})")
    return handler


async def main(address: str, channel: int) -> None:
    print(f"Conectando em {address} (canal MIDI {channel}) ...")
    async with BleakClient(address) as client:
        print(f"Conectado: {client.is_connected}")

        # Subscribe to both notify channels to catch any state/battery feedback.
        await client.start_notify(VENDOR_NOTIFY, _make_handler("ae42(vendor)"))
        await client.start_notify(MIDI_IO, _make_handler("midi"))
        print("Notificações assinadas (ae42 + midi). Escutando 3s de baseline...")
        await asyncio.sleep(3.0)

        # The MIDI char is readable — dump whatever it returns.
        try:
            raw = await client.read_gatt_char(MIDI_IO)
            print(f"read midi char: {raw.hex()}  ({list(raw)})")
        except Exception as exc:  # noqa: BLE001 - recon, surface anything
            print(f"read midi char falhou: {exc!r}")

        print("\n>>> Enviando Program Changes. OLHE O PEDAL trocar de preset. <<<\n")
        for prog in PROGRAMS:
            frame = program_change_frame(prog, channel)
            print(f"  -> Program Change preset_idx={prog} (frame {frame.hex()})")
            await client.write_gatt_char(MIDI_IO, frame, response=False)
            await asyncio.sleep(5.0)

        print("\nFim da sequência. Escutando mais 3s por notificações tardias...")
        await asyncio.sleep(3.0)
        await client.stop_notify(VENDOR_NOTIFY)
        await client.stop_notify(MIDI_IO)


if __name__ == "__main__":
    addr = sys.argv[1]
    ch = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    if len(sys.argv) > 3:
        PROGRAMS = [int(a) for a in sys.argv[3:]]
    asyncio.run(main(addr, ch))
