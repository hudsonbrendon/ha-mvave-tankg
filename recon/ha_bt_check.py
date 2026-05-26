"""Probe a Home Assistant instance's Bluetooth view over the WebSocket API.

Usage: python recon/ha_bt_check.py <TOKEN> [host]

Authenticates, lists the bluetooth/esphome config entries (adapters + proxies),
subscribes to live advertisements for ~12 s, and reports every device HA sees —
grouped by source (adapter/proxy) — flagging anything that looks like a Tank-G.
"""
import asyncio
import json
import sys

import websockets

HOST = sys.argv[2] if len(sys.argv) > 2 else "homeassistant.local:8123"
TOKEN = sys.argv[1]
URI = f"ws://{HOST}/api/websocket"


def _walk(obj):
    """Yield dicts that look like a BLE service info (have address + name keys)."""
    if isinstance(obj, dict):
        if "address" in obj and ("name" in obj or "rssi" in obj):
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


async def main():
    async with websockets.connect(URI, max_size=None) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print("AUTH FAILED:", auth)
            return
        print("AUTH ok — HA", auth.get("ha_version"))

        # 1) config entries: bluetooth adapters + esphome proxies
        await ws.send(json.dumps({"id": 1, "type": "config_entries/get"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1 and msg.get("type") == "result":
                for e in msg.get("result", []):
                    if e.get("domain") in ("bluetooth", "esphome"):
                        print(f"  entry: {e.get('domain'):10} {e.get('title')!r:40} state={e.get('state')}")
                break

        # 2) live advertisements
        await ws.send(json.dumps({"id": 2, "type": "bluetooth/subscribe_advertisements"}))
        seen = {}  # address -> (name, source, rssi)
        print("Coletando advertisements por 12s...")
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=12.0))
                if msg.get("type") != "event":
                    continue
                for si in _walk(msg.get("event")):
                    addr = si.get("address")
                    seen[addr] = (
                        si.get("name") or "?",
                        si.get("source", "?"),
                        si.get("rssi"),
                    )
        except asyncio.TimeoutError:
            pass

        print(f"\n{len(seen)} dispositivos BLE vistos pelo HA:")
        sources = {}
        for addr, (name, source, rssi) in sorted(
            seen.items(), key=lambda kv: (kv[1][1], -(kv[1][2] or -999))
        ):
            tank = "  <<< TANK-G" if "tank" in name.lower() else ""
            print(f"  src={source}  {addr}  rssi={rssi}  name={name!r}{tank}")
            sources.setdefault(source, 0)
            sources[source] += 1
        print("\nfontes (adaptadores/proxies):", sources)
        if not any("tank" in n.lower() for n, _, _ in seen.values()):
            print(">>> Nenhum TANK-G no alcance do rádio do HA agora.")


asyncio.run(main())
