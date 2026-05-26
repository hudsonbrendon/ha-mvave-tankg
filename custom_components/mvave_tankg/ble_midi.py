"""Pure BLE-MIDI framing helpers (no Home Assistant deps)."""
from __future__ import annotations

_BLE_MIDI_HEADER = 0x80
_BLE_MIDI_TIMESTAMP = 0x80


def program_change_frame(program: int, channel: int = 0) -> bytes:
    """Build a BLE-MIDI packet carrying a single Program Change message.

    program: MIDI program number (0-127). channel: MIDI channel (0-15).
    """
    status = 0xC0 | (channel & 0x0F)
    return bytes([_BLE_MIDI_HEADER, _BLE_MIDI_TIMESTAMP, status, program & 0x7F])
