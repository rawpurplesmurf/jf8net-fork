# jf8net

Async and synchronous Python client library (`v0.3.1`) for the **[`jf8call-fork`](../jf8call-fork)** (`v0.7.1+`) JSON WebSocket API, with full typed dataclass coverage for network `rigctld` CAT/PTT, `DATA-U` display offset (`data_offset_hz` / `carrier_freq_khz`), 2-minute clear-bin passband allocation, JS8 Heartbeat Networking, store-and-forward inbox messaging, ADIF QSO logging, and live `~12 Hz` spectrum streaming.

## About This Fork

This repository is a cleaned-up, maintained fork of [`jfrancis42/jf8net`](https://github.com/jfrancis42/jf8net) by Jeff Francis (N0GQ), updated alongside [`jf8call-fork`](../jf8call-fork). Key cleanup, security, and API improvements in this fork include:

- **Security & Code Hygiene:** Upgraded dependency floors (`websockets >= 17.4`, `setuptools >= 78.1.1`, `pip >= 26.2.1`), resolved `ruff` and `bandit` lint/security findings, removed obsolete NOAA solar weather helpers, and added `tls` (`wss://`) connection support.
- **Expanded `v0.7.0` / `v0.7.1` Station API:** Added `halt_tx()`, `connect_rigctld()`, 2-minute clear-bin passband helpers (`get_passband()`, `find_clear_freq()`), Heartbeat Networking (`get_heartbeats()`, `send_heartbeat_ack()`, `MessageType.HEARTBEAT_ACK`), QSO log helpers, and `DATA-U` carrier-offset fields (`data_offset_hz`, `carrier_freq_khz`, `dial_freq_khz`, `spot_freq_khz`).
- **Automated Test Suite:** Added an offline `pytest` unit test suite (`tests/test_jf8net.py`) with ≥ 80% coverage enforcement.

---

## Installation & Local Development

```bash
git clone <repo-url> jf8net
cd jf8net
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools
pip install -e .

# For development, linting, security checks & offline unit tests:
pip install -r requirements-dev.txt
ruff check .
bandit -r jf8net/
pytest --cov=jf8net --cov-fail-under=80
```

**Requirements:** Python `3.10+`, `websockets >= 17.4`.

---

## Quick Start

### Async (`JF8Client`)

```python
import asyncio
from jf8net import DecodedMessage, JF8Client


async def main() -> None:
    async with JF8Client(host="localhost", port=2102) as client:
        print(await client.get_status())

        @client.on_message
        async def handle(msg: DecodedMessage) -> None:
            print(f"{msg.from_call} -> {msg.to or '*'}: {msg.body} ({msg.snr_db:+d} dB)")

        await client.run_forever()


asyncio.run(main())
```

### Synchronous (`JF8ClientSync`)

```python
from jf8net.sync import JF8ClientSync

with JF8ClientSync(host="localhost", port=2102) as client:
    print(client.get_status())
    for msg in client.messages():
        print(msg)
```

---

## API Highlights

### Station & Heartbeat Configuration

```python
await client.set_config(
    callsign="W5XYZ",
    grid="DM79AA",
    rigctld="127.0.0.1:4532",
    data_offset_hz=1500,  # e.g. +1500 Hz for Yaesu FT-991 DATA-USB (0 for standard USB / Icom)
    station_info="100W Dipole",
    station_status="QRV JS8",
    groups=["@ALL", "@ALLCALL", "@ARES"],
    heartbeat_enabled=True,
    heartbeat_interval_mins=10,
    heartbeat_sub_channel=True,
    heartbeat_ack_enabled=True,
    clear_bin_window_secs=120,
    auto_reply=True,
    tx_enabled=True,
)
```

### Network `rigctld` & VFO Control

```python
await client.connect_rigctld("127.0.0.1:4532")
await client.set_frequency(14078.0)
await client.tune()  # RIG_OP_TUNE via CAT
```

### 2-Minute Clear-Bin Selection, Heartbeats & Emergency Halt

```python
# Inspect occupied 50 Hz passband bins over the last 120 seconds
pb = await client.get_passband(clear_secs=120)

# Pick (and apply) an audio offset clear of both JS8 decodes and RF energy for >= 120s
spot = await client.find_clear_freq(min_hz=1000.0, max_hz=2400.0, clear_secs=120, apply=True)

# Queue a directed message on that clear offset
await client.send("W4ABC HELLO 73", submode="normal", tx_freq_hz=spot.freq_hz)

# Send @HB or an explicit 1-frame HEARTBEAT SNR acknowledgement
await client.send_heartbeat()
await client.send_heartbeat_ack("W4ABC", snr_db=-10, caller_freq_hz=715.0)

# Immediate emergency TX stop (flushes audio buffer, unkeys PTT, clears queue)
await client.halt_tx()
```

### Store-and-Forward Inbox & QSO Log

```python
# Direct MSG or relay via an intermediate JS8 station ("K0XYZ MSG TO:W4ABC ...")
await client.inbox_send("W4ABC", "QSL MEET 0300Z", via="K0XYZ")
msg_id = await client.inbox_store("W4ABC", "STORED FOR PICKUP")
inbox = await client.get_inbox()

# QSO logging & ADIF 3 export
await client.add_qso("W4ABC", grid="EM73", snr_db=-10, notes="20m JS8 Normal")
adif_text = await client.export_adif()
```

---

## Events & Decorators

| Event | Decorator | Argument Type |
| :--- | :--- | :--- |
| `message.decoded` | `@client.on_message` | `DecodedMessage` |
| `message.frame` | `@client.on_frame` | `FrameUpdate` |
| `heartbeat.updated` | `@client.on_heartbeat_updated` | `list[HeartbeatEntry]` |
| `inbox.updated` | `@client.on_inbox_updated` | `dict` |
| `status` | `@client.on_status` | `Status` |
| `spectrum` | `@client.on_spectrum` | `Spectrum` |
| `tx.started` / `tx.finished` | `@client.on_tx_started` / `on_tx_finished` | `dict` |
| `radio.connected` / `radio.disconnected` | `@client.on_radio_connected` / `on_radio_disconnected` | `dict` |
| `config.changed` | `@client.on_config_changed` | `dict` |

---

## Multi-Instance Monitoring Example

```python
import asyncio
from jf8net import DecodedMessage, JF8Client

STATIONS = [
    ("localhost", 2102, "rig-hf"),
    ("192.0.2.20", 2102, "rig-vhf"),
]


async def watch(host: str, port: int, label: str) -> None:
    async with JF8Client(host=host, port=port) as client:
        @client.on_message
        def handle(msg: DecodedMessage) -> None:
            print(f"[{label}] {msg}")

        await client.run_forever()


async def main() -> None:
    await asyncio.gather(*(watch(*s) for s in STATIONS))


asyncio.run(main())
```

---

## License

**GPL-3.0-or-later** (matching JF8Call).
