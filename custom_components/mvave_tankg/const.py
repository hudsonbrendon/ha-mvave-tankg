"""Constants for the M-Vave Tank-G integration."""
from __future__ import annotations

DOMAIN = "mvave_tankg"

# BLE-MIDI (padrão Apple/BLE-MIDI — confirmado no recon, ver docs/PROTOCOL.md)
MIDI_SERVICE_UUID = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
MIDI_IO_CHAR_UUID = "7772e5db-3868-4112-a1a9-f2669d106bf3"

# Bateria padrão: recon NÃO encontrou o serviço 0x180F no Tank-G.
BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
HAS_STANDARD_BATTERY = False  # Task A2: serviço 0x180F ausente

# Preset (confirmado ao vivo no recon — Program Change canal 0, programa 0-35)
MIDI_CHANNEL = 0          # canal observado no recon
PRESET_COUNT = 36         # Tank-G tem 36 presets (A1-D9)
PRESET_UI_OFFSET = 1      # preset N na UI (1-36) = programa N-1 (0-35)
