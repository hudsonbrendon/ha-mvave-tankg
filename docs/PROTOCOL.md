# M-Vave Tank-G — Protocolo BLE (recon)

> Fonte da verdade do protocolo. Saída da **Fase A** do plano. As Fases C/D leem deste arquivo.

## Identidade

- **Nome BLE (local_name):** `TANK-Gv2_BLE`
- **Address (macOS / CoreBluetooth UUID):** `406548D0-4739-D906-DBFB-BFF5C80667E8`
  - ⚠️ No macOS o `address` do bleak é um UUID interno do CoreBluetooth, **não** o MAC real.
    Se o Home Assistant rodar em Linux, refazer o scan no host do HA para pegar o MAC real
    (e ajustar o matcher por `local_name`, que é portável).
- **Manufacturer data observado:** company id `26995`, bytes `6e636f`
- **Como colocar em modo anúncio:** segurar footswitches **B+C por 3 s** → indicador BT **piscando**
  (apagado = BT off, piscando = on/sem conexão, fixo = conectado). Fechar o app MVAVE no celular
  antes, senão o pedal conecta nele e não anuncia para o PC.

## Serviços / Características observados (GATT)

```
[service] 0000ae40-0000-1000-8000-00805f9b34fb  (Vendor specific)
    [char] 0000ae41-0000-1000-8000-00805f9b34fb  props=[write-without-response]
    [char] 0000ae42-0000-1000-8000-00805f9b34fb  props=[notify]
        [desc] 00002902-0000-1000-8000-00805f9b34fb   (CCCD)
[service] 03b80e5a-ede8-4b33-a751-6ce34ec4c700  (BLE-MIDI)
    [char] 7772e5db-3868-4112-a1a9-f2669d106bf3  props=[write-without-response,notify,read]
        [desc] 00002902-0000-1000-8000-00805f9b34fb   (CCCD)
```

## Battery Service 0x180F presente? (sim/não)

**Não.** O serviço `0000180f-...` / char `00002a19-...` **não** foi listado.
→ `HAS_STANDARD_BATTERY = False`.

**Veredito final (bateria descartada):** o app oficial M-Vave **não exibe bateria** de forma
alguma. Como o app tem acesso completo ao protocolo BLE do pedal, a ausência de qualquer
indicação de bateria no app confirma que o Tank-G **não reporta nível de bateria por BLE** —
existe só o aviso físico no display ("L"/"LO") e o LED de carga (vermelho→azul). Bateria no
Home Assistant é **inviável**; não adianta capturar para isso.

## Característica BLE-MIDI presente? (sim/não + UUID)

**Sim.** Serviço `03b80e5a-ede8-4b33-a751-6ce34ec4c700`,
característica de I/O `7772e5db-3868-4112-a1a9-f2669d106bf3`
(props `write-without-response`, `notify`, `read`). Bate exatamente com as constantes do plano
(`MIDI_SERVICE_UUID`, `MIDI_IO_CHAR_UUID`).

## Controle de preset (BLE-MIDI) — CONFIRMADO ao vivo

Testado enviando Program Change e observando o pedal (recon/preset_test.py).

- **Característica de escrita:** `7772e5db-3868-4112-a1a9-f2669d106bf3` (`write-without-response`)
- **Tipo de mensagem:** Program Change (status `0xC0`)
- **Canal MIDI:** 0
- **Frame BLE-MIDI:** `80 80 C0 <program>` — header `0x80`, timestamp `0x80`, status `0xC0`, programa.
- **Faixa de programa:** 0–35 (36 presets).
- **Mapeamento programa → preset (banco-major, 4 por banco):**
  - `programa = (banco - 1) * 4 + posição`, posição A=0, B=1, C=2, D=3, banco 1–9.
  - Display do pedal mostra o **banco** = `programa // 4 + 1`; footswitch aceso = `programa % 4` (A/B/C/D).
  - Verificado: `prog 0 → A1` (footswitch A), `prog 27 → D7` (footswitch D, display "7").
- **One-way:** o pedal NÃO notifica troca de preset e a leitura da char MIDI volta vazia
  (`read midi char: []`). A entidade `number` do HA reflete apenas o último valor enviado.
- **Constantes p/ const.py:** `MIDI_CHANNEL = 0`, `PRESET_COUNT = 36`, `PRESET_UI_OFFSET = 1`
  (UI 1–36 → programa 0–35). `HAS_STANDARD_BATTERY = False`.

## Serviço vendor 0xAE40 (não previsto no plano)

Canal proprietário provável do app MVAVE oficial:
- `0000ae41` — escrita (`write-without-response`): comandos do app.
- `0000ae42` — notificação (`notify`): respostas/estado do pedal (candidato a **bateria** e estado de preset).

A Task A3 (captura HCI snoop com o app oficial) deve revelar se preset/LED/bateria passam por
`0xAE40` (vendor) ou pelo BLE-MIDI `7772e5db`. Capturar e decodificar os frames de ambos.

## Pendências para a Task A3 (HCI snoop no Android)

- [x] ~~Frames de troca de preset~~ → confirmado ao vivo: Program Change canal 0 (acima).
- [x] ~~Canal MIDI e mapeamento preset → programa~~ → canal 0, `prog = (banco-1)*4 + pos`.
- [ ] Frames de cor do LED por preset (provável vendor `ae41` ou SysEx).
- [ ] Query/resposta de bateria (provável `ae41` write → `ae42` notify) e o índice do byte da %.

Só **LED** e **bateria** dependem do HCI snoop. Presença, RSSI e **preset** já estão prontos
para virar código (Fase B/C/D) sem Android.

## Sonda sem Android (recon/cuvave_probe.py) — resultado

Tentativa de descobrir bateria/estado sem capturar o app, usando o framing Cuvave conhecido
(`F0 00 32 ... F7`, ver Referências). Conectado ao pedal, assinados os notifies de `ae42`
(vendor) e `7772e5db` (MIDI), foram enviados comandos **de consulta** nos dois transportes:

| Comando | ae41 (raw) | MIDI (framed) | Resposta |
|---|---|---|---|
| MIDI Identity Request `F0 7E 7F 06 01 F7` | enviado | enviado | **nenhuma** |
| Cuvave discovery `F0 00 32 45 ...` | enviado | enviado | **nenhuma** |
| Cuvave settings `F0 00 32 0D 41 ...` | enviado | enviado | **nenhuma** |

Também **nenhuma notificação espontânea** em 6 s de escuta (sem heartbeat de estado/bateria).

**Conclusão:** o Tank-G não responde aos comandos da Chocolate nem ao Identity Request, e não
empurra estado sozinho. Os opcodes específicos do Tank-G (bateria/LED/nome de preset) só saem
capturando o app oficial (Task A3 — HCI snoop no Android) e decodificando com o framing
`F0 00 32 ... F7`. Provável que o app faça um handshake inicial pela char vendor `ae41` que
"abre" o canal `ae42` — sem replicá-lo, o vendor fica mudo.

## Referências (família Cuvave/M-Vave)

- Framing SysEx Cuvave: `F0 00 32 [cmd] [dados] [checksum] F7`, manufacturer id `00 32`.
  Fonte: https://github.com/cbix/mvave-chocolate-sysex (engenharia reversa da Chocolate).
- A Chocolate confirmou que "SysEx pela char BLE-MIDI padrão não funciona" — coerente com o
  Tank-G usar o serviço vendor `0xAE40` (`ae41`/`ae42`) como canal real de config.
