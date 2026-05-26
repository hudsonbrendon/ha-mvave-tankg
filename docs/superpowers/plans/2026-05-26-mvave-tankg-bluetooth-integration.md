# Integração M-Vave Tank-G (Bluetooth) para Home Assistant — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa-a-tarefa. Os passos usam checkbox (`- [ ]`) para rastreio.

**Goal:** Criar uma integração custom (HACS) para o Home Assistant que descobre a pedaleira M-VAVE Tank-G via Bluetooth LE, expõe presença/RSSI, bateria (se o recon confirmar) e controle de preset/cor de LED via BLE-MIDI.

**Architecture:** Integração `custom_components/mvave_tankg` usando a stack `bluetooth`/`bleak` nativa do HA. Um `DataUpdateCoordinator` conecta sob demanda via `bleak-retry-connector` para ler bateria e enviar comandos BLE-MIDI; um callback de advertisement alimenta presença/RSSI sem conectar. As constantes específicas do protocolo (UUIDs de bateria, frames SysEx) são **descobertas na Fase A (reconhecimento)** e gravadas em `const.py`.

**Tech Stack:** Python 3.12+, Home Assistant ≥ 2024.8, `bleak`, `bleak-retry-connector`, `pytest` + `pytest-homeassistant-custom-component`, Wireshark/nRF Connect (recon), HACS.

---

## Realidade de viabilidade (ler antes de começar)

O Tank-G é uma **pedaleira de guitarra M-VAVE (Cuvave)**. O Bluetooth dela tem dois papéis: (1) **áudio A2DP** (entrada de som) e (2) **BLE-MIDI** para o app oficial editar presets, IRs e cor do LED. O mesmo padrão BLE-MIDI dos controladores M-Vave "Chocolate".

| Objetivo do usuário | Viável? | Como |
|---|---|---|
| Detectar via BT (presença) | ✅ Sim | Advertisement BLE captado pelo HA |
| RSSI / "por perto" | ✅ Sim | Advertisement BLE |
| Nível de bateria | ⚠️ Condicional | Só se a Fase A achar Battery Service `0x180F` **ou** um SysEx de query |
| Trocar preset | ⚠️ Condicional | BLE-MIDI Program Change (Fase A confirma canal/char) |
| Cor do LED | ⚠️ Condicional | BLE-MIDI SysEx (Fase A captura os bytes) |
| **Detectar carregando** | ❌ Não | É LED físico (vermelho/azul), não dado BLE |
| **Ligar o pedal** | ❌ Não | Rádio desligado quando off — impossível acordar por BLE |
| **Desligar o pedal** | ❌ Improvável | Sem comando conhecido; só se a Fase A revelar um |

As fases C/D são **gated** pelo resultado da Fase A. Se o recon não achar bateria, a Fase C entrega apenas o sensor de RSSI/última-vez-visto e a tarefa de bateria é pulada (documentado em cada tarefa).

---

## Estrutura de arquivos

```
ha-mvave-tankg/
├── custom_components/
│   └── mvave_tankg/
│       ├── __init__.py            # setup/unload do entry, cria coordinator
│       ├── manifest.json          # metadados + matcher bluetooth + requirements
│       ├── const.py               # DOMAIN + constantes do protocolo (preenchidas no recon)
│       ├── ble_midi.py            # helpers puros: framing/parse BLE-MIDI (testável sem HA)
│       ├── coordinator.py         # DataUpdateCoordinator: conecta via bleak, lê bateria, envia comandos
│       ├── config_flow.py         # descoberta bluetooth + confirmação
│       ├── binary_sensor.py       # presença (conectável/por perto)
│       ├── sensor.py              # RSSI + bateria (se houver)
│       ├── number.py              # preset atual (Program Change)
│       └── strings.json           # textos do config flow
├── tests/
│   ├── conftest.py
│   ├── test_ble_midi.py           # unit: framing/parse (sem harness HA)
│   └── test_config_flow.py        # config flow via pytest-homeassistant-custom-component
├── docs/
│   ├── PROTOCOL.md                # saída da Fase A (recon) — fonte da verdade do protocolo
│   └── superpowers/plans/2026-05-26-mvave-tankg-bluetooth-integration.md
├── hacs.json
├── requirements_test.txt
└── README.md
```

Responsabilidades: `ble_midi.py` é puro e 100% testável isolado (é onde mora a lógica de protocolo). `coordinator.py` concentra todo I/O BLE. As entidades (`*_sensor.py`, `number.py`) só leem do coordinator. `config_flow.py` só cuida de descoberta/setup. Arquivos pequenos e focados.

---

## FASE A — Reconhecimento (você executa; desbloqueia bateria e controle)

> Estas tarefas produzem `docs/PROTOCOL.md`. As Fases C/D leem dele. Sem isso, só presença é possível. Nenhuma escreve código de produção ainda.

### Task A1: Capturar identidade BLE do pedal (nome + MAC + serviços)

**Files:**
- Create: `docs/PROTOCOL.md`
- Create: `recon/scan.py` (script descartável de recon)

- [ ] **Step 1: Ligar o pedal e ativar Bluetooth nele**

No Tank-G, pressione o footswitch PRESET para ativar o Bluetooth. O indicador BT pisca (pareando) e fica fixo quando conectado. Mantenha o pedal **ligado e perto** (mesmo cômodo do PC que vai rodar o scan).

- [ ] **Step 2: Instalar o bleak num venv local de recon**

```bash
cd ~/Github/ha-mvave-tankg
python3 -m venv .venv-recon
source .venv-recon/bin/activate
pip install bleak
```

- [ ] **Step 3: Escrever o script de scan**

Create `recon/scan.py`:

```python
"""Scan BLE devices and dump services/characteristics for a chosen address."""
import asyncio
import sys
from bleak import BleakClient, BleakScanner


async def scan() -> None:
    print("Scanning 10s...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    for address, (dev, adv) in devices.items():
        print(f"{address}  name={dev.name!r}  rssi={adv.rssi}  "
              f"service_uuids={adv.service_uuids}  "
              f"manufacturer_data={dict(adv.manufacturer_data)}")


async def enumerate_gatt(address: str) -> None:
    async with BleakClient(address) as client:
        for service in client.services:
            print(f"[service] {service.uuid}  {service.description}")
            for char in service.characteristics:
                print(f"    [char] {char.uuid}  props={char.properties}")
                for desc in char.descriptors:
                    print(f"        [desc] {desc.uuid}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        asyncio.run(enumerate_gatt(sys.argv[1]))
    else:
        asyncio.run(scan())
```

- [ ] **Step 4: Rodar o scan e anotar o pedal**

Run: `python recon/scan.py`
Expected: uma linha com `name='TANK-G...'` (ou similar). **Anote o `address` (MAC) exato** e o `name` exato.

- [ ] **Step 5: Enumerar serviços/características do pedal**

Run: `python recon/scan.py <MAC_DO_PEDAL>`
Expected: lista de serviços. Procure especificamente:
- Serviço BLE-MIDI `03b80e5a-ede8-4b33-a751-6ce34ec4c700` com característica `7772e5db-3868-4112-a1a9-f2669d106bf3` (props `write-without-response`, `notify`).
- Serviço de bateria padrão `0000180f-0000-1000-8000-00805f9b34fb` com característica `00002a19-...` (Battery Level).

> macOS nota: o `address` do bleak no macOS é um UUID interno do CoreBluetooth, não o MAC real. Anote esse UUID — é o que o HA também usará nessa máquina. Se o HA roda em Linux, refaça o scan no host do HA (ou via proxy) para pegar o MAC real.

- [ ] **Step 6: Registrar achados no PROTOCOL.md**

Create/edit `docs/PROTOCOL.md`:

```markdown
# M-Vave Tank-G — Protocolo BLE (recon)

## Identidade
- Nome BLE (local_name): `TANK-G...`   <!-- preencher exato da Task A1 -->
- Address: `XX:XX:...`                  <!-- MAC no Linux / UUID no macOS -->

## Serviços/Características observados
<!-- colar saída da Task A1 Step 5 -->

## Battery Service 0x180F presente? (sim/não)
<!-- preencher -->

## Característica BLE-MIDI presente? (sim/não + UUID)
<!-- preencher -->
```

- [ ] **Step 7: Commit**

```bash
git add docs/PROTOCOL.md recon/scan.py
git commit -m "recon: capture Tank-G BLE identity and GATT table"
```

---

### Task A2: Verificar bateria via Battery Service padrão

**Files:**
- Modify: `docs/PROTOCOL.md`
- Create: `recon/read_battery.py`

- [ ] **Step 1: Decidir o caminho a partir da Task A1**

Se a Task A1 Step 5 **listou** o serviço `0000180f-...`, siga os passos abaixo. Se **não listou**, escreva em `docs/PROTOCOL.md` "Battery Service 0x180F ausente — bateria depende de SysEx (Task A3)" e pule para a Task A3.

- [ ] **Step 2: Escrever o leitor de bateria**

Create `recon/read_battery.py`:

```python
"""Read standard Battery Level characteristic (0x2A19)."""
import asyncio
import sys
from bleak import BleakClient

BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        raw = await client.read_gatt_char(BATTERY_LEVEL_UUID)
        print(f"battery raw={raw.hex()}  percent={int(raw[0])}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
```

- [ ] **Step 3: Ler com o pedal em ~3 níveis diferentes**

Run: `python recon/read_battery.py <ADDRESS>`
Expected: `battery raw=XX percent=NN`. Repita com bateria cheia, média e baixa para confirmar que o valor varia e bate com a realidade.

- [ ] **Step 4: Registrar no PROTOCOL.md**

Edit `docs/PROTOCOL.md` adicionando:

```markdown
## Bateria
- Método: Battery Service padrão
- Char UUID: 00002a19-0000-1000-8000-00805f9b34fb
- Formato: uint8 = porcentagem (0-100)
- Conferido em 3 níveis: sim
```

- [ ] **Step 5: Commit**

```bash
git add docs/PROTOCOL.md recon/read_battery.py
git commit -m "recon: confirm standard battery service on Tank-G"
```

---

### Task A3: Capturar protocolo do app (presets, LED, bateria-via-SysEx)

> Necessária para controle de preset/LED, e para bateria caso a Task A2 não tenha achado o serviço padrão. Usa o app oficial M-VAVE no Android + log HCI snoop.

**Files:**
- Modify: `docs/PROTOCOL.md`

- [ ] **Step 1: Habilitar o log HCI snoop no Android**

No celular Android: Configurações → Sobre o telefone → toque 7x em "Número da versão" (libera Opções do desenvolvedor) → Opções do desenvolvedor → ative **"Ativar registro de captura de HCI Bluetooth"**. Depois **desligue e religue o Bluetooth** para começar um log limpo.

- [ ] **Step 2: Reproduzir ações isoladas no app M-VAVE**

Pareie o app com o Tank-G. Faça **uma ação por vez, com pausa de ~3s entre elas**, anotando a ordem num papel:
1. Trocar para o preset 1 → preset 2 → preset 5.
2. Mudar a cor do LED (ex.: vermelho → azul → verde).
3. Abrir a tela que mostra a bateria (se o app mostrar %).

- [ ] **Step 3: Extrair o log e abrir no Wireshark**

Gere um bug report e extraia o `btsnoop_hci.log`:

```bash
adb bugreport tankg_capture.zip
# o log fica em FS/data/misc/bluetooth/logs/btsnoop_hci.log dentro do zip
unzip -o tankg_capture.zip -d tankg_capture
```

Abra o `btsnoop_hci.log` no Wireshark.

- [ ] **Step 4: Filtrar e decodificar as escritas ATT**

No Wireshark, filtro: `btatt.opcode == 0x52 || btatt.opcode == 0x12` (Write Command / Write Request). Para cada ação anotada, encontre o pacote correspondente e copie o **value** (bytes) escrito na característica BLE-MIDI.

Decodifique o framing BLE-MIDI de cada value:
- Byte 0: header `0x80 | (timestampHigh & 0x3F)`.
- Byte 1: `0x80 | (timestampLow & 0x7F)`.
- Bytes seguintes: mensagem MIDI. Program Change = `0xC0|canal`, `programa`. Control Change = `0xB0|canal`, `cc`, `valor`. SysEx = `0xF0 ... 0xF7`.

Exemplo realista de Program Change para preset 2, canal 0: value `80 80 c0 01` (preset é 0-indexado → programa `01`).

- [ ] **Step 5: Registrar TODOS os frames no PROTOCOL.md**

Edit `docs/PROTOCOL.md`:

```markdown
## Controle de preset (BLE-MIDI)
- Característica de escrita: 7772e5db-3868-4112-a1a9-f2669d106bf3
- Tipo de mensagem: Program Change  (status 0xC0)
- Canal MIDI observado: 0
- Mapeamento preset→programa: preset N (UI) → programa N-1
- Frames capturados:
  - preset 1: 80 80 c0 00
  - preset 2: 80 80 c0 01
  - preset 5: 80 80 c0 04

## Cor do LED
- Tipo: SysEx (ou CC — preencher o que foi observado)
- Frames capturados:
  - vermelho: 80 80 f0 ...  <!-- colar bytes reais -->
  - azul:     80 80 f0 ...
  - verde:    80 80 f0 ...

## Bateria via SysEx (se aplicável)
- Query enviada pelo app: 80 80 f0 ...      <!-- colar -->
- Resposta (notify) do pedal: 80 80 f0 ...  <!-- colar -->
- Byte da porcentagem na resposta: índice K  <!-- identificar -->
```

- [ ] **Step 6: Commit**

```bash
git add docs/PROTOCOL.md
git commit -m "recon: decode Tank-G app BLE-MIDI frames (preset/LED/battery)"
```

---

## FASE B — Scaffold da integração + presença (não depende do recon)

### Task B1: Estrutura do repositório e metadados HACS

**Files:**
- Create: `custom_components/mvave_tankg/manifest.json`
- Create: `hacs.json`
- Create: `custom_components/mvave_tankg/const.py`
- Create: `README.md`

- [ ] **Step 1: Inicializar git (se ainda não fez na Fase A)**

```bash
cd ~/Github/ha-mvave-tankg
git init
```

- [ ] **Step 2: Escrever o manifest.json**

> Ordem das chaves importa pro `hassfest`: `domain` primeiro, `name` segundo, o resto em ordem alfabética.

Create `custom_components/mvave_tankg/manifest.json`:

```json
{
  "domain": "mvave_tankg",
  "name": "M-Vave Tank-G",
  "bluetooth": [
    { "local_name": "TANK-G*", "connectable": true }
  ],
  "codeowners": ["@hudsonbrendon"],
  "config_flow": true,
  "dependencies": ["bluetooth_adapters"],
  "documentation": "https://github.com/hudsonbrendon/ha-mvave-tankg",
  "integration_type": "device",
  "iot_class": "local_push",
  "requirements": ["bleak-retry-connector>=3.5.0"],
  "version": "0.1.0"
}
```

> Ajuste `"local_name"` para casar exatamente com o nome capturado na Task A1 (use `*` como curinga se houver sufixo variável).

- [ ] **Step 3: Escrever o hacs.json**

Create `hacs.json`:

```json
{
  "name": "M-Vave Tank-G",
  "render_readme": true,
  "homeassistant": "2024.8.0"
}
```

- [ ] **Step 4: Escrever o const.py inicial**

Create `custom_components/mvave_tankg/const.py`:

```python
"""Constants for the M-Vave Tank-G integration."""
from __future__ import annotations

DOMAIN = "mvave_tankg"

# BLE-MIDI (padrão Apple/BLE-MIDI — fixo, não depende do recon)
MIDI_SERVICE_UUID = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
MIDI_IO_CHAR_UUID = "7772e5db-3868-4112-a1a9-f2669d106bf3"

# Bateria padrão (usado se a Task A2 confirmou o serviço 0x180F)
BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
HAS_STANDARD_BATTERY = True  # ajustar conforme Task A2

# Preset (preenchido pela Task A3)
MIDI_CHANNEL = 0          # canal observado no recon
PRESET_COUNT = 36         # Tank-G tem 36 presets
PRESET_UI_OFFSET = 1      # preset N na UI = programa N-1 (offset 1) — confirmar no recon
```

- [ ] **Step 5: Escrever README mínimo**

Create `README.md`:

```markdown
# M-Vave Tank-G — Home Assistant

Integração custom (HACS) para a pedaleira M-VAVE Tank-G via Bluetooth LE.

Expõe presença, RSSI, bateria (quando disponível) e controle de preset.
Limitações físicas: não liga/desliga o pedal nem detecta carregamento (LED físico).

## Instalação
HACS → Integrações → repositório custom `hudsonbrendon/ha-mvave-tankg`.
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/mvave_tankg/manifest.json custom_components/mvave_tankg/const.py hacs.json README.md
git commit -m "feat: scaffold mvave_tankg integration metadata"
```

---

### Task B2: Helpers puros de BLE-MIDI (TDD)

**Files:**
- Create: `custom_components/mvave_tankg/ble_midi.py`
- Test: `tests/test_ble_midi.py`
- Create: `requirements_test.txt`

- [ ] **Step 1: Criar requirements de teste**

Create `requirements_test.txt`:

```
pytest
pytest-asyncio
pytest-homeassistant-custom-component
```

Run: `pip install -r requirements_test.txt`

- [ ] **Step 2: Escrever o teste que falha**

Create `tests/test_ble_midi.py`:

```python
from custom_components.mvave_tankg.ble_midi import program_change_frame


def test_program_change_frame_preset_one():
    # preset UI 1 -> programa 0, canal 0
    assert program_change_frame(program=0, channel=0) == bytes([0x80, 0x80, 0xC0, 0x00])


def test_program_change_frame_preset_five():
    assert program_change_frame(program=4, channel=0) == bytes([0x80, 0x80, 0xC0, 0x04])


def test_program_change_frame_other_channel():
    assert program_change_frame(program=2, channel=3) == bytes([0x80, 0x80, 0xC3, 0x02])


def test_program_change_masks_to_7_bits():
    # programa nunca pode estourar 7 bits no MIDI
    assert program_change_frame(program=200, channel=0)[3] == 200 & 0x7F
```

- [ ] **Step 3: Rodar o teste e ver falhar**

Run: `pytest tests/test_ble_midi.py -v`
Expected: FAIL com `ModuleNotFoundError` ou `ImportError: cannot import name 'program_change_frame'`.

- [ ] **Step 4: Implementar o mínimo**

Create `custom_components/mvave_tankg/ble_midi.py`:

```python
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
```

- [ ] **Step 5: Rodar o teste e ver passar**

Run: `pytest tests/test_ble_midi.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add custom_components/mvave_tankg/ble_midi.py tests/test_ble_midi.py requirements_test.txt
git commit -m "feat: add BLE-MIDI program change framing helper"
```

---

### Task B3: Config flow por descoberta Bluetooth (TDD)

**Files:**
- Create: `custom_components/mvave_tankg/config_flow.py`
- Create: `custom_components/mvave_tankg/strings.json`
- Test: `tests/test_config_flow.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Criar conftest habilitando custom integrations**

Create `tests/conftest.py`:

```python
import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
```

- [ ] **Step 2: Escrever o teste de config flow que falha**

Create `tests/test_config_flow.py`:

```python
from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mvave_tankg.const import DOMAIN

SERVICE_INFO = BluetoothServiceInfoBleak(
    name="TANK-G",
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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TANK-G"
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL — config flow não existe ainda (`Invalid handler specified` ou import error).

- [ ] **Step 4: Implementar o config flow**

Create `custom_components/mvave_tankg/config_flow.py`:

```python
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

from .const import DOMAIN


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
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            return self.async_create_entry(title=self._discovery.name, data={})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery.name},
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
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current:
                continue
            if info.name and info.name.upper().startswith("TANK-G"):
                self._discovered[info.address] = info.name

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )
```

- [ ] **Step 5: Criar strings.json**

Create `custom_components/mvave_tankg/strings.json`:

```json
{
  "config": {
    "flow_title": "{name}",
    "step": {
      "bluetooth_confirm": {
        "description": "Adicionar a pedaleira {name}?"
      },
      "user": {
        "data": { "address": "Dispositivo" }
      }
    },
    "abort": {
      "no_devices_found": "Nenhum Tank-G encontrado por perto. Ligue o pedal e ative o Bluetooth (footswitch PRESET).",
      "already_configured": "Este dispositivo já está configurado."
    }
  }
}
```

- [ ] **Step 6: Rodar e ver passar**

Run: `pytest tests/test_config_flow.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add custom_components/mvave_tankg/config_flow.py custom_components/mvave_tankg/strings.json tests/test_config_flow.py tests/conftest.py
git commit -m "feat: add bluetooth discovery config flow"
```

---

### Task B4: Setup do entry + binary_sensor de presença

**Files:**
- Create: `custom_components/mvave_tankg/__init__.py`
- Create: `custom_components/mvave_tankg/binary_sensor.py`

- [ ] **Step 1: Implementar __init__.py (setup/unload mínimo)**

Create `custom_components/mvave_tankg/__init__.py`:

```python
"""The M-Vave Tank-G integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TankGCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.NUMBER,
]

type TankGConfigEntry = ConfigEntry[TankGCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TankGConfigEntry) -> bool:
    coordinator = TankGCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TankGConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
```

> `coordinator.py` é criado na Task C1. Esta task depende de C1 para o entry carregar. Se executar B4 antes de C1, o import falhará — implemente C1 imediatamente após, ou reordene B4 para depois de C1. (Recomendado: fazer C1 antes de testar o carregamento do entry.)

- [ ] **Step 2: Implementar binary_sensor de presença**

Create `custom_components/mvave_tankg/binary_sensor.py`:

```python
"""Presence binary sensor for the Tank-G."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TankGPresence(entry.runtime_data)])


class TankGPresence(CoordinatorEntity[TankGCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Presença"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_presence"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return self.coordinator.present
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/mvave_tankg/__init__.py custom_components/mvave_tankg/binary_sensor.py
git commit -m "feat: add entry setup and presence binary sensor"
```

---

## FASE C — Coordinator (presença/RSSI sempre; bateria se recon confirmou)

### Task C1: Coordinator com callback de advertisement (presença/RSSI)

**Files:**
- Create: `custom_components/mvave_tankg/coordinator.py`

- [ ] **Step 1: Implementar o coordinator base**

Create `custom_components/mvave_tankg/coordinator.py`:

```python
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

from .const import (
    BATTERY_LEVEL_CHAR_UUID,
    DOMAIN,
    HAS_STANDARD_BATTERY,
    MIDI_IO_CHAR_UUID,
)
from .ble_midi import program_change_frame

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
```

> Se a Task A2 escreveu `HAS_STANDARD_BATTERY = False` em `const.py`, `_async_update_data` simplesmente não lê bateria — o sensor de bateria (Task C2) não será adicionado. Bateria via SysEx (caso a Task A3 tenha capturado) seria um incremento futuro: substituir `_read_battery` por uma escrita do frame de query + leitura da notificação no índice K documentado.

- [ ] **Step 2: Verificar que o entry carrega**

Run: `pytest tests/test_config_flow.py -v`
Expected: PASS (imports do coordinator resolvem; nada quebrou).

- [ ] **Step 3: Commit**

```bash
git add custom_components/mvave_tankg/coordinator.py
git commit -m "feat: add coordinator with presence tracking and battery/preset BLE access"
```

---

### Task C2: Sensores de RSSI e bateria

**Files:**
- Create: `custom_components/mvave_tankg/sensor.py`

- [ ] **Step 1: Implementar sensores**

Create `custom_components/mvave_tankg/sensor.py`:

```python
"""RSSI and battery sensors for the Tank-G."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .const import HAS_STANDARD_BATTERY
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[CoordinatorEntity] = [TankGRssi(coordinator)]
    if HAS_STANDARD_BATTERY:
        entities.append(TankGBattery(coordinator))
    async_add_entities(entities)


class TankGRssi(CoordinatorEntity[TankGCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sinal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_rssi"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.rssi


class TankGBattery(CoordinatorEntity[TankGCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Bateria"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_battery"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("battery")
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/mvave_tankg/sensor.py
git commit -m "feat: add RSSI and battery sensors"
```

---

## FASE D — Controle de preset (depende da Task A3)

### Task D1: Entidade number para trocar preset

**Files:**
- Create: `custom_components/mvave_tankg/number.py`

- [ ] **Step 1: Confirmar mapeamento do recon**

Abra `docs/PROTOCOL.md` (Task A3). Confirme `MIDI_CHANNEL`, `PRESET_COUNT` e `PRESET_UI_OFFSET` em `const.py` batem com os frames capturados. Se o app usou Control Change em vez de Program Change, adicione um `control_change_frame` em `ble_midi.py` (com teste, no mesmo molde da Task B2) e use-o no coordinator. Caso contrário, prossiga.

- [ ] **Step 2: Implementar a entidade number**

Create `custom_components/mvave_tankg/number.py`:

```python
"""Preset selector (number) for the Tank-G via BLE-MIDI Program Change."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankGConfigEntry
from .const import PRESET_COUNT, PRESET_UI_OFFSET
from .coordinator import TankGCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankGConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TankGPreset(entry.runtime_data)])


class TankGPreset(CoordinatorEntity[TankGCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Preset"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_min_value = 1

    def __init__(self, coordinator: TankGCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_preset"
        self._attr_device_info = coordinator.device_info
        self._attr_native_max_value = PRESET_COUNT
        self._current: int | None = None

    @property
    def native_value(self) -> int | None:
        # BLE-MIDI Program Change é one-way; refletimos o último valor enviado.
        return self._current

    async def async_set_native_value(self, value: float) -> None:
        ui_preset = int(value)
        program = ui_preset - PRESET_UI_OFFSET
        await self.coordinator.async_send_program_change(program)
        self._current = ui_preset
        self.async_write_ha_state()
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/mvave_tankg/number.py
git commit -m "feat: add preset number entity (BLE-MIDI program change)"
```

> **Cor do LED:** se a Task A3 capturou SysEx de cor, adicionar depois uma plataforma `select` (cores fixas observadas) ou `light` que escreve os frames SysEx exatos do `PROTOCOL.md` via um novo método `async_send_sysex(frame: bytes)` no coordinator (mesmo molde de `async_send_program_change`). Fora do escopo mínimo; documentar o procedimento em `PROTOCOL.md` antes de implementar.

---

## FASE E — Empacotamento e validação final

### Task E1: hassfest + hacs validation locais

**Files:**
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Workflow de validação**

Create `.github/workflows/validate.yml`:

```yaml
name: Validate
on: [push, pull_request]
jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
```

- [ ] **Step 2: Rodar a suíte de testes completa**

Run: `pytest -v`
Expected: todos os testes passam (test_ble_midi + test_config_flow).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: add hassfest and HACS validation"
```

- [ ] **Step 4: Teste de fumaça no HA real**

Copie `custom_components/mvave_tankg/` para o `config/custom_components/` do seu HA (ou instale via HACS como repo custom). Reinicie o HA. Com o pedal ligado e BT ativo, confirme:
- Notificação de descoberta "M-Vave Tank-G" aparece → adicione.
- `binary_sensor.*_presenca` fica `on` quando o pedal está por perto.
- `sensor.*_sinal` mostra RSSI.
- `sensor.*_bateria` mostra % (se `HAS_STANDARD_BATTERY = True`).
- Mudar `number.*_preset` troca o preset no pedal.

---

## Self-review (cobertura do escopo)

- ✅ Detectar via BT → Task B3 (config flow por descoberta) + B4/C1 (presença).
- ✅ Status bateria → Task A2 (recon) + C1/C2 (sensor), gated.
- ✅ Configurações (trocar preset) → Task A3 (recon) + D1. Cor do LED documentada como extensão pós-recon.
- ✅ "Carregando" / ligar / desligar → explicitamente marcados inviáveis na seção de viabilidade (física do BLE), com justificativa.
- ✅ Tipos consistentes: `program_change_frame(program, channel)`, `TankGCoordinator.async_send_program_change`, `.present`, `.rssi`, `.device_info`, `HAS_STANDARD_BATTERY`, `PRESET_UI_OFFSET` usados igualmente entre tarefas.
- ⚠️ Dependência de ordem sinalizada: B4 importa de `coordinator.py` (C1) — fazer C1 antes de testar o carregamento do entry.
- ⚠️ Constantes de protocolo (`MIDI_CHANNEL`, frames de LED, método de bateria) são **dados de recon**, não placeholders: a Fase A entrega valores reais com procedimento de captura + exemplo a substituir.
