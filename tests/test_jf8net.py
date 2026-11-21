"""Offline unit tests for jf8net (>= 80% statement coverage without network sockets)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
import websockets.exceptions

import jf8net
from jf8net import (
    AudioDevices,
    BandEntry,
    ClearFreqResult,
    Config,
    ConnectionError,
    DecodedMessage,
    FrameType,
    FrameUpdate,
    HeartbeatEntry,
    InboxMessage,
    JF8Client,
    JF8Error,
    MessageType,
    ModemType,
    PassbandState,
    PttType,
    QsoEntry,
    RadioStatus,
    Spectrum,
    Status,
    TxFrame,
    VersionInfo,
)
from jf8net._parsers import (
    config_kwargs_to_api,
    parse_band_entry,
    parse_clear_freq_result,
    parse_config,
    parse_decoded_message,
    parse_frame_update,
    parse_heartbeat_entry,
    parse_inbox_message,
    parse_passband_state,
    parse_qso_entry,
    parse_radio_status,
    parse_spectrum,
    parse_status,
    parse_tx_frame,
    parse_version_info,
)
from jf8net.sync import JF8ClientSync


class FakeWebSocket:
    """In-memory fake WebSocket protocol for offline testing."""

    def __init__(self, initial_frames: list[dict[str, Any]] | None = None) -> None:
        self.closed = False
        self.sent: list[dict[str, Any]] = []
        self._incoming: asyncio.Queue[str | BaseException] = asyncio.Queue()
        self.auto_reply: dict[str, dict[str, Any]] = {}
        self.fail_cmd: str | None = None
        for frame in initial_frames or [
            {"type": "hello", "data": {"version": "1.0"}},
            {
                "type": "event",
                "event": "status",
                "data": {
                    "callsign": "W5XYZ",
                    "grid": "DM79",
                    "submode": 0,
                    "submode_name": "Normal",
                    "frequency_khz": 14078.0,
                    "tx_freq_hz": 1500.0,
                    "transmitting": False,
                    "audio_running": True,
                    "radio_connected": True,
                    "radio_freq_khz": 14078.0,
                    "radio_mode": "USB",
                    "rigctld": "127.0.0.1:4532",
                    "tx_queue_size": 0,
                    "heartbeat_enabled": True,
                    "heartbeat_interval_mins": 10,
                    "heartbeat_ack_enabled": True,
                    "clear_bin_window_secs": 120,
                    "auto_reply": True,
                    "ws_port": 2102,
                    "ws_clients": 1,
                },
            },
        ]:
            self._incoming.put_nowait(json.dumps(frame))

    def push_event(self, event: str, data: dict[str, Any]) -> None:
        self._incoming.put_nowait(json.dumps({"type": "event", "event": event, "data": data}))

    def push_raw(self, raw: str | BaseException) -> None:
        self._incoming.put_nowait(raw)

    async def recv(self) -> str:
        item = await self._incoming.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def send(self, payload: str) -> None:
        msg = json.loads(payload)
        self.sent.append(msg)
        cmd = msg.get("cmd", "")
        cmd_id = msg.get("id", "")
        if cmd == self.fail_cmd:
            self._incoming.put_nowait(
                json.dumps({"type": "reply", "id": cmd_id, "ok": False, "error": "rig busy"})
            )
            return
        if cmd == "timeout.test":
            return
        reply_data = self.auto_reply.get(cmd, {})
        self._incoming.put_nowait(
            json.dumps({"type": "reply", "id": cmd_id, "ok": True, "data": reply_data})
        )

    async def close(self) -> None:
        self.closed = True
        self._incoming.put_nowait(websockets.exceptions.ConnectionClosed(None, None))


def test_models_and_parsers() -> None:
    assert jf8net.__version__ == "0.3.1"
    assert MessageType.name(MessageType.HEARTBEAT) == "Heartbeat"
    assert MessageType.name(MessageType.HEARTBEAT_ACK) == "HeartbeatAck"
    assert MessageType.name(999) == "Unknown"
    assert FrameType.name(FrameType.SINGLE) == "single"
    assert FrameType.name(99) == "99"
    assert ModemType.name(ModemType.GFSK8) == "JS8/GFSK8"
    assert PttType.CAT == 1

    msg = parse_decoded_message(
        {
            "utc_iso": "2026-11-19T23:00:00Z",
            "freq_hz": 1523.4,
            "snr_db": -8,
            "submode": 0,
            "submode_name": "Normal",
            "from": "W4ABC",
            "to": "W5XYZ",
            "body": "HEARTBEAT SNR -08",
            "raw": "W4ABC: W5XYZ HEARTBEAT SNR -08",
            "type": MessageType.HEARTBEAT_ACK,
            "type_name": "HeartbeatAck",
            "grid": "EM73",
            "heard_me": True,
        }
    )
    assert isinstance(msg, DecodedMessage)
    assert msg.freq_key == 152
    assert msg.is_directed is True
    assert msg.is_heartbeat is False
    assert msg.is_heartbeat_ack is True
    assert "W4ABC -> W5XYZ" in str(msg)

    hb = parse_decoded_message({"utc_iso": "bad-date", "to": "@HB", "type": MessageType.HEARTBEAT})
    assert hb.is_directed is False
    assert hb.is_heartbeat is True

    frame = parse_frame_update(
        {
            "utc_iso": "",
            "freq_hz": 1000.0,
            "snr_db": -12,
            "submode": 1,
            "submode_name": "Fast",
            "frame_type": FrameType.FIRST,
            "frame_text": "W5XYZ",
            "assembled_text": "W5XYZ HELLO",
            "is_complete": False,
        }
    )
    assert isinstance(frame, FrameUpdate)
    assert frame.freq_key == 100
    assert frame.frame_type_name == "first"
    assert "FIRST" in str(frame)

    st = parse_status(
        {
            "callsign": "W5XYZ",
            "grid": "DM79",
            "frequency_khz": 14079.5,
            "carrier_freq_khz": 14078.0,
            "data_offset_hz": 1500,
            "radio_connected": True,
            "busy_slots": [{"hz": 700, "age_secs": 15.0, "call": "W4ABC"}],
        }
    )
    assert isinstance(st, Status)
    assert st.carrier_freq_khz == 14078.0
    assert st.data_offset_hz == 1500
    assert len(st.busy_slots) == 1
    assert "W5XYZ" in str(st)

    pb = parse_passband_state(
        {"busy_slots": [{"hz": 700, "age_secs": 12.0}], "clear_window_secs": 120, "bandwidth_hz": 50.0}
    )
    assert isinstance(pb, PassbandState)
    assert pb.clear_window_secs == 120

    cf = parse_clear_freq_result({"freq_hz": 1540.0, "all_clear": True, "clear_window_secs": 120})
    assert isinstance(cf, ClearFreqResult)
    assert cf.freq_hz == 1540.0

    hbe = parse_heartbeat_entry({"callsign": "W4ABC", "grid": "EM73", "snr_db": -10, "freq_hz": 720.0})
    assert isinstance(hbe, HeartbeatEntry)
    assert hbe.callsign == "W4ABC"

    band = parse_band_entry({"name": "20m", "freqKhz": 14078.0, "txFreqHz": 1500.0})
    assert isinstance(band, BandEntry)
    assert "20m" in str(band)

    qso = parse_qso_entry({"id": "1", "time": "2026-11-19T23:00:00Z", "callsign": "W4ABC"})
    assert isinstance(qso, QsoEntry)

    inbox = parse_inbox_message(
        {"id": 7, "utc_iso": "2026-11-19T23:00:00Z", "from": "W4ABC", "to": "W5XYZ", "body": "HI"}
    )
    assert isinstance(inbox, InboxMessage)
    assert "(unread)" in str(inbox)

    cfg = parse_config(
        {
            "callsign": "W5XYZ",
            "grid": "DM79",
            "groups": ["@ALL", "@ARES"],
            "heartbeatAckEnabled": True,
            "clearBinWindowSecs": 120,
            "bandList": [{"name": "40m"}],
        }
    )
    assert isinstance(cfg, Config)
    assert cfg.groups == ["@ALL", "@ARES"]
    assert cfg.heartbeat_ack_enabled is True
    assert len(cfg.band_list) == 1
    assert parse_config({"groups": None}).groups == ["@ALL", "@ALLCALL"]

    rs = parse_radio_status(
        {"connected": True, "freq_khz": 14078.0, "mode": "USB", "rigctld": "127.0.0.1:4532", "ptt_type": 1}
    )
    assert isinstance(rs, RadioStatus)
    assert "USB" in str(rs)

    txf = parse_tx_frame({"payload": "ABC", "frame_type": FrameType.LAST, "submode": 0, "tx_freq_hz": 1420.0})
    assert isinstance(txf, TxFrame)
    assert txf.frame_type_name == "last"
    assert txf.tx_freq_hz == 1420.0

    ver = parse_version_info({"version": "0.7.0", "major": 0, "minor": 7, "patch": 0})
    assert isinstance(ver, VersionInfo)
    assert str(ver) == "0.7.0"

    devs = AudioDevices(inputs=["in1"], outputs=["out1"])
    assert devs.inputs == ["in1"]

    spec = parse_spectrum({"bins": [-80.0, -35.0, -60.0], "bin_count": 3, "hz_per_bin": 10.0})
    assert isinstance(spec, Spectrum)
    assert spec.peak_hz() == 10.0
    assert spec.peak_db() == -35.0
    assert spec.slice(5.0, 15.0) == [-80.0, -35.0]
    empty_spec = Spectrum(bins=[], bin_count=0, hz_per_bin=0.0, sample_rate=12000.0)
    assert empty_spec.peak_hz() == 0.0
    assert empty_spec.peak_db() == 0.0
    assert empty_spec.slice(0.0, 100.0) == []

    mapped = config_kwargs_to_api(
        {
            "callsign": "W5XYZ",
            "pskReporterEnabled": True,
            "heartbeat_ack_enabled": True,
            "clear_bin_window_secs": 120,
            "rigctld": "127.0.0.1:4532",
        }
    )
    assert mapped["heartbeatAckEnabled"] is True
    assert mapped["clearBinWindowSecs"] == 120
    assert mapped["rigctld"] == "127.0.0.1:4532"
    with pytest.raises(ValueError, match="Unknown config field"):
        config_kwargs_to_api({"invalid_field": 1})


async def test_async_client_commands_and_events() -> None:
    fake_ws = FakeWebSocket()
    fake_ws.auto_reply.update(
        {
            "status.get": {"callsign": "W5XYZ", "grid": "DM79", "ws_port": 2102},
            "config.get": {"callsign": "W5XYZ", "grid": "DM79", "pskReporterEnabled": True},
            "config.set": {"callsign": "W5XYZ", "grid": "DM79", "autoAtu": True},
            "audio.devices": {"input": ["pulse_in"], "output": ["pulse_out"]},
            "radio.get": {"connected": True, "freq_khz": 14078.0, "mode": "USB"},
            "radio.connect": {"connected": True, "freq_khz": 14078.0, "mode": "USB", "rigctld": "127.0.0.1:4532"},
            "radio.frequency.set": {"freq_khz": 7078.0},
            "messages.get": {"messages": [{"from": "W4ABC", "to": "W5XYZ", "body": "SNR -05"}]},
            "spectrum.get": {"bins": [-70.0, -40.0], "bin_count": 2, "hz_per_bin": 5.86},
            "passband.get": {"busy_slots": [{"hz": 700, "age_secs": 10.0}], "clear_window_secs": 120},
            "tx.find_clear": {"freq_hz": 1550.0, "all_clear": True, "clear_window_secs": 120},
            "heartbeats.get": {"heartbeats": [{"callsign": "W4ABC", "grid": "EM73", "snr_db": -10}]},
            "tx.send": {"queue_size": 2, "tx_freq_hz": 1550.0},
            "tx.hb": {"queue_size": 1, "freq_hz": 720.0},
            "tx.hb_ack": {"queue_size": 1, "freq_hz": 780.0},
            "tx.snr": {"queue_size": 1},
            "tx.info": {"queue_size": 1},
            "tx.status": {"queue_size": 1},
            "tx.grid": {"queue_size": 1},
            "tx.hearing": {"queue_size": 1},
            "tx.queue.get": {"queue": [{"payload": "TEST", "frame_type": 3, "submode": 0}]},
            "bands.get": {"bands": [{"name": "20m", "freqKhz": 14078.0, "txFreqHz": 1500.0}]},
            "bands.set": {"count": 1},
            "version.get": {"version": "0.7.0", "major": 0, "minor": 7, "patch": 0},
            "qso.log.get": {"qsos": [{"id": "1", "callsign": "W4ABC", "grid": "EM73"}]},
            "qso.log.add": {"total": 2},
            "qso.log.delete": {"deleted": True},
            "qso.log.adif": {"adif": "<CALL:5>W4ABC<EOR>"},
            "inbox.get": {"messages": [{"id": 3, "from": "W4ABC", "to": "W5XYZ", "body": "HELLO"}]},
            "inbox.send": {"queued": True, "queue_size": 1},
            "inbox.store": {"id": "9"},
        }
    )

    async def fake_connect(uri: str) -> FakeWebSocket:
        assert uri == "wss://127.0.0.1:2102"
        return fake_ws

    received_events: list[Any] = []
    received_specs: list[Spectrum] = []
    received_hbs: list[list[HeartbeatEntry]] = []

    with patch("jf8net._client.websockets.connect", side_effect=fake_connect):
        async with JF8Client("127.0.0.1", 2102, tls=True, auto_reconnect=False, cmd_timeout=0.2) as c:
            assert c.connected is True
            assert c.cached_status is not None

            c.on("*", received_events.append)
            c.on_spectrum(received_specs.append)
            c.on_heartbeat_updated(received_hbs.append)
            c.on_inbox_updated(received_events.append)

            assert (await c.get_status()).callsign == "W5XYZ"
            assert (await c.get_config()).psk_reporter_enabled is True
            cfg_updated = await c.set_config(auto_atu=True, data_offset_hz=1500)
            assert cfg_updated.auto_atu is True
            assert (await c.get_audio_devices()).inputs == ["pulse_in"]
            await c.restart_audio()
            assert (await c.get_radio()).connected is True
            assert (await c.connect_rigctld("127.0.0.1:4532")).rigctld == "127.0.0.1:4532"
            radio_res = await c.connect_radio(
                rig_model=3073,
                port="/dev/ttyUSB0",
                baud=19200,
                ptt_type=1,
                data_bits=8,
                stop_bits=1,
                parity=0,
                handshake=0,
                dtr_state=0,
                rts_state=0,
            )
            assert radio_res.connected is True
            await c.disconnect_radio()
            assert await c.set_frequency(7078.0) == 7078.0
            await c.set_ptt(False)
            await c.tune()
            assert len(await c.get_messages()) == 1
            await c.clear_messages()
            assert (await c.get_spectrum()).bin_count == 2
            assert len((await c.get_passband(clear_secs=120)).busy_slots) == 1
            assert (await c.find_clear_freq(min_hz=500.0, max_hz=2400.0, preferred_hz=1500.0, clear_secs=120, avoid_hz=700.0, apply=True)).freq_hz == 1550.0
            assert len(await c.get_heartbeats()) == 1
            await c.clear_heartbeats()
            assert await c.send("W4ABC HELLO", submode="fast", tx_freq_hz=1550.0) == 2
            assert await c.send_heartbeat() == 1
            assert (await c.send_heartbeat_ack("w4abc", -10, caller_freq_hz=710.0)).freq_hz == 780.0
            assert await c.send_snr_query("w4abc") == 1
            assert await c.send_info_query("w4abc") == 1
            assert await c.send_status_query("w4abc") == 1
            assert await c.send_grid_query("w4abc") == 1
            assert await c.send_hearing_query("w4abc") == 1
            assert len(await c.get_tx_queue()) == 1
            await c.clear_tx_queue()
            await c.halt_tx()
            assert any(msg.get("cmd") == "tx.halt" for msg in fake_ws.sent)
            assert len(await c.get_bands()) == 1
            assert await c.set_bands([BandEntry("20m", 14078.0, 1500.0)]) == 1
            assert (await c.get_version()).version == "0.7.0"
            assert len(await c.get_qso_log()) == 1
            assert await c.add_qso("w4abc", grid="em73", snr_db=-10, notes="JS8") == 2
            assert await c.delete_qso(1) is True
            assert "W4ABC" in await c.export_adif()
            assert len(await c.get_inbox("w5xyz")) == 1
            assert await c.inbox_send("w4abc", "73", via="k0xyz") is True
            assert await c.inbox_store("w4abc", "MSG") == "9"
            await c.inbox_mark_read(3)
            await c.inbox_delete(3)

            fake_ws.push_event("message.decoded", {"from": "N0CALL", "to": "W5XYZ", "body": "ACK"})
            fake_ws.push_event("message.frame", {"frame_type": 1, "assembled_text": "HI"})
            fake_ws.push_event("spectrum", {"bins": [-50.0], "bin_count": 1, "hz_per_bin": 5.0})
            fake_ws.push_event("heartbeat.updated", {"heartbeats": [{"callsign": "W4ABC"}]})
            fake_ws.push_event("inbox.updated", {})
            fake_ws.push_event("config.changed", {"callsign": "W5XYZ"})
            await asyncio.sleep(0.05)

            async def trigger_finish() -> None:
                await asyncio.sleep(0.02)
                fake_ws.push_event("tx.finished", {})

            finish_task = asyncio.create_task(trigger_finish())
            await c.send_and_wait("W4ABC TEST", timeout=1.0)
            await finish_task

            fake_ws.fail_cmd = "radio.tune"
            with pytest.raises(JF8Error, match="rig busy"):
                await c.tune()

            with pytest.raises(JF8Error, match="timed out"):
                await c._cmd("timeout.test")

    assert len(received_specs) == 1
    assert len(received_hbs) == 1
    assert any(isinstance(e, DecodedMessage) for e in received_events)


async def test_connection_errors() -> None:
    c = JF8Client("127.0.0.1", 2199, auto_reconnect=False)
    with pytest.raises(ConnectionError, match="Not connected"):
        await c.get_status()

    async def fail_connect(_uri: str) -> Any:
        raise OSError("refused")

    with (
        patch("jf8net._client.websockets.connect", side_effect=fail_connect),
        pytest.raises(ConnectionError, match="Cannot connect"),
    ):
        await c.connect()


def test_sync_client_wrapper() -> None:
    holder: dict[str, FakeWebSocket] = {}

    async def fake_connect(_uri: str) -> FakeWebSocket:
        ws = FakeWebSocket()
        ws.auto_reply.update(
            {
                "status.get": {"callsign": "W5XYZ", "grid": "DM79"},
                "config.get": {"callsign": "W5XYZ", "grid": "DM79"},
                "radio.connect": {"connected": True, "rigctld": "127.0.0.1:4532"},
                "passband.get": {"busy_slots": [], "clear_window_secs": 120},
                "tx.find_clear": {"freq_hz": 1500.0, "all_clear": True},
                "heartbeats.get": {"heartbeats": []},
                "tx.hb_ack": {"freq_hz": 740.0, "queue_size": 1},
                "tx.send": {"queue_size": 1},
                "tx.halt": {},
                "version.get": {"version": "0.7.0"},
                "qso.log.add": {"total": 1},
                "qso.log.delete": {"deleted": True},
                "inbox.get": {"messages": []},
            }
        )
        holder["ws"] = ws
        return ws

    with (
        patch("jf8net._client.websockets.connect", side_effect=fake_connect),
        JF8ClientSync("127.0.0.1", 2102, auto_reconnect=False) as sc,
    ):
            assert sc.cached_status is not None
            assert sc.get_status().callsign == "W5XYZ"
            assert sc.get_config().grid == "DM79"
            assert sc.connect_rigctld("127.0.0.1:4532").connected is True
            assert sc.get_passband().clear_window_secs == 120
            assert sc.find_clear_freq(apply=True).freq_hz == 1500.0
            assert sc.get_heartbeats() == []
            sc.clear_heartbeats()
            assert sc.send_heartbeat_ack("W4ABC", -8).freq_hz == 740.0
            assert sc.send("W4ABC 73", tx_freq_hz=1500.0) == 1
            sc.halt_tx()
            assert any(msg.get("cmd") == "tx.halt" for msg in holder["ws"].sent)
            assert sc.get_version().version == "0.7.0"
            assert sc.add_qso("W4ABC", grid="EM73") == 1
            assert sc.delete_qso(1) is True
            assert sc.get_inbox() == []
            assert sc._loop is not None
            sc._loop.call_soon_threadsafe(
                sc._loop.call_later,
                0.01,
                holder["ws"].push_event,
                "message.decoded",
                {
                    "utc_iso": datetime.now(timezone.utc).isoformat(),
                    "from": "W4ABC",
                    "to": "W5XYZ",
                    "body": "73",
                },
            )
            items = list(sc.messages(timeout=0.06))
            assert len(items) == 1
            assert items[0].from_call == "W4ABC"
