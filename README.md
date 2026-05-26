# M-Vave Tank-G — Home Assistant

Integração custom (HACS) para a pedaleira M-VAVE Tank-G via Bluetooth LE.

Expõe presença, RSSI e controle de preset (BLE-MIDI Program Change).

## Recursos

| Recurso | Status |
|---|---|
| Detecção via Bluetooth (descoberta) | ✅ |
| Presença / "por perto" (binary_sensor) | ✅ |
| RSSI (sensor) | ✅ |
| Trocar preset 1–36 (number) | ✅ |
| Nível de bateria | ❌ pedal não expõe o Battery Service `0x180F` |
| Cor do LED | ⏳ requer recon adicional (HCI snoop) |
| Ligar/desligar o pedal | ❌ impossível por BLE (rádio off quando desligado) |

## Instalação

HACS → Integrações → repositório custom `hudsonbrendon/ha-mvave-tankg`.

Para descoberta: ligue o pedal e ative o Bluetooth (segure os footswitches **B+C por 3 s**
até o LED de BT piscar).

## Protocolo

O protocolo BLE observado está documentado em [`docs/PROTOCOL.md`](docs/PROTOCOL.md).
