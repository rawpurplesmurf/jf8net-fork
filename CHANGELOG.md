# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-11-20

### Added

- Added `data_offset_hz` and `carrier_freq_khz` fields on `Status` and `data_offset_hz` on `Config` / `set_config()` (`dataOffsetHz`) for `JF8Call v0.7.1` `DATA-U` transceiver VFO display offset support.
- Added `dial_freq_khz` and `spot_freq_khz` fields on `DecodedMessage` and `FrameUpdate`.

### Changed

- Expanded `README.md` with complete virtual environment setup, editable installation, linting (`ruff`, `bandit`), and unit test (`pytest --cov=jf8net`) instructions.

## [0.3.0] - 2026-11-19

### Added

- Added `JF8Call v0.7.0` 2-minute clear-bin and Heartbeat Networking API support on both `JF8Client` and `JF8ClientSync`:
  - `connect_rigctld(endpoint)` shorthand for network `rigctld` (`RIG_MODEL_NETRIGCTL`, CAT PTT).
  - `get_passband()` (`PassbandState` / `PassbandSlot`) and `find_clear_freq()` (`ClearFreqResult`) for 120-second RF + decode clear-bin allocation.
  - `get_heartbeats()`, `clear_heartbeats()`, `send_heartbeat_ack()`, and `on_heartbeat_updated` (`HeartbeatEntry`).
  - `MessageType.HEARTBEAT_ACK` (`21`), `DecodedMessage.is_heartbeat_ack`, `tx_freq_hz` override on `send()` / `send_and_wait()`, `via` relay support on `inbox_send()`, `add_qso()`, `delete_qso()`, and `on_inbox_updated`.
  - Expanded `Status`, `Config`, and `RadioStatus` dataclasses (`rigctld`, `heartbeat_ack_enabled`, `clear_bin_window_secs`, `groups`, `ws_host`, `web_host`, `web_port`, `busy_slots`).

### Changed

- Updated `README.md` reference documentation (`websockets>=17.4`, `heartbeat_interval_mins`, 2-minute clear-bin TX examples, and full `MessageType` `0..21` table).

## [0.2.0] - 2026-11-19

### Added

- Added `JF8Client.halt_tx()` and `JF8ClientSync.halt_tx()` (`tx.halt` mid-frame PTT unkey & queue clear).
- Added `tls: bool = False` (`wss://`) option on `JF8Client` / `JF8ClientSync` using `urllib.parse.urlunsplit`.
- Added offline `pytest` unit test suite (`tests/test_jf8net.py`, `>= 88%` coverage) and `requirements-dev.txt`.

### Changed

- Upgraded dependency floors to `websockets>=17.4`, `setuptools>=78.1.1`, and `pip>=26.2.1`.
- Removed obsolete NOAA solar weather helpers (`SolarData`, `get_solar()`).
- Resolved `ruff` and `bandit` lint/security findings across `jf8net/` and `examples/`.
