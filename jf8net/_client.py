"""
jf8net._client — Async WebSocket client for the JF8Call API.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import urlunsplit

import websockets
import websockets.exceptions

from ._models import (
    AudioDevices,
    BandEntry,
    ClearFreqResult,
    Config,
    DecodedMessage,
    HeartbeatEntry,
    InboxMessage,
    PassbandState,
    QsoEntry,
    RadioStatus,
    Spectrum,
    Status,
    TxFrame,
    VersionInfo,
)
from ._parsers import (
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

logger = logging.getLogger(__name__)

Handler = Callable[[Any], Any]


class JF8Error(Exception):
    """Raised when the JF8Call API returns ok=false."""


class ConnectionError(JF8Error):
    """Raised when the WebSocket connection fails or is lost."""


class JF8Client:
    """Async WebSocket client for JF8Call."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2102,
        *,
        tls: bool = False,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0,
        cmd_timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._tls = tls
        self._auto_reconnect = auto_reconnect
        self._reconnect_delay = reconnect_delay
        self._cmd_timeout = cmd_timeout

        self._ws: Any = None
        self._recv_task: asyncio.Task[None] | None = None
        self._running = False

        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._handlers: dict[str, list[Handler]] = {}
        self._status: Status | None = None

    def _build_uri(self) -> str:
        scheme = "wss" if self._tls else "ws"
        return urlunsplit((scheme, f"{self._host}:{self._port}", "", "", ""))

    async def connect(self) -> None:
        """Open the WebSocket connection and start the receive pump."""
        uri = self._build_uri()
        try:
            self._ws = await websockets.connect(uri)
        except (OSError, websockets.exceptions.WebSocketException, ValueError) as exc:
            raise ConnectionError(f"Cannot connect to JF8Call at {uri}: {exc}") from exc

        try:
            await self._ws.recv()  # hello
            raw = await self._ws.recv()  # status event
            obj = json.loads(raw)
            if obj.get("event") == "status":
                self._status = parse_status(obj.get("data", {}))
        except (OSError, ValueError, websockets.exceptions.WebSocketException) as exc:
            logger.debug("Initial handshake drain incomplete: %s", exc)

        self._running = True
        self._recv_task = asyncio.create_task(self._recv_loop(), name="jf8net-recv")
        logger.debug("Connected to JF8Call at %s", uri)

    async def disconnect(self) -> None:
        """Close the connection and stop the receive pump."""
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (
                asyncio.CancelledError,
                OSError,
                websockets.exceptions.WebSocketException,
            ) as exc:
                logger.debug("Receive task stopped: %s", exc)
            self._recv_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        logger.debug("Disconnected from JF8Call")

    async def __aenter__(self) -> JF8Client:  # noqa: PYI034
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket connection is active."""
        if self._ws is None:
            return False
        if hasattr(self._ws, "closed"):
            return not bool(self._ws.closed)
        return getattr(self._ws, "close_code", None) is None

    @property
    def cached_status(self) -> Status | None:
        """Most recent status received (updated every second from the status event)."""
        return self._status

    async def _recv_loop(self) -> None:
        while self._running:
            try:
                raw = await self._ws.recv()
                msg = json.loads(raw)
                await self._dispatch(msg)
            except websockets.exceptions.ConnectionClosed:
                if not self._running:
                    break
                logger.warning("JF8Call connection closed")
                if self._auto_reconnect:
                    await self._reconnect()
                else:
                    break
            except asyncio.CancelledError:
                break
            except (
                OSError,
                ValueError,
                TypeError,
                websockets.exceptions.WebSocketException,
            ) as exc:
                logger.warning("Receive error: %s", exc)

    async def _reconnect(self) -> None:
        self._ws = None
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        while self._running:
            await asyncio.sleep(self._reconnect_delay)
            logger.info("Reconnecting to JF8Call...")
            try:
                uri = self._build_uri()
                self._ws = await websockets.connect(uri)
                await self._ws.recv()  # hello
                await self._ws.recv()  # status
                logger.info("Reconnected")
                return
            except (OSError, ValueError, websockets.exceptions.WebSocketException) as exc:
                logger.warning("Reconnect failed: %s", exc)

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("type")

        if msg_type == "reply":
            msg_id = str(msg.get("id", ""))
            fut = self._pending.get(msg_id)
            if fut and not fut.done():
                fut.set_result(msg)
            return

        if msg_type != "event":
            return

        event = str(msg.get("event", ""))
        raw_data = msg.get("data", {})

        if event == "status":
            self._status = parse_status(raw_data)

        typed: Any = raw_data
        if event == "message.decoded":
            typed = parse_decoded_message(raw_data)
        elif event == "message.frame":
            typed = parse_frame_update(raw_data)
        elif event == "status":
            typed = self._status
        elif event == "heartbeat.updated":
            typed = [parse_heartbeat_entry(h) for h in raw_data.get("heartbeats", [])]
        elif event == "config.changed":
            typed = raw_data

        for handler in self._handlers.get(event, []) + self._handlers.get("*", []):
            try:
                result = handler(typed)
                if inspect.isawaitable(result):
                    await result
            except (RuntimeError, TypeError, ValueError, OSError, JF8Error) as exc:
                logger.warning("Handler error for event %r: %s", event, exc)

    async def _cmd(self, cmd: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.connected:
            raise ConnectionError("Not connected to JF8Call")
        cmd_id = str(uuid.uuid4())[:8]
        msg: dict[str, Any] = {"type": "cmd", "id": cmd_id, "cmd": cmd}
        if data:
            msg["data"] = data
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[cmd_id] = fut
        try:
            await self._ws.send(json.dumps(msg))
            reply = await asyncio.wait_for(asyncio.shield(fut), timeout=self._cmd_timeout)
        except asyncio.TimeoutError:
            raise JF8Error(f"Command {cmd!r} timed out after {self._cmd_timeout}s") from None
        finally:
            self._pending.pop(cmd_id, None)
        if not reply.get("ok"):
            raise JF8Error(str(reply.get("error", "unknown error")))
        return dict(reply.get("data") or {})

    def on(self, event: str, handler: Handler | None = None) -> Any:
        """Register a handler for a named event. Can be used as a decorator."""

        def decorator(fn: Handler) -> Handler:
            self._handlers.setdefault(event, []).append(fn)
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    def off(self, event: str, handler: Handler) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def on_message(self, fn: Handler) -> Handler:
        return self.on("message.decoded", fn)

    def on_frame(self, fn: Handler) -> Handler:
        return self.on("message.frame", fn)

    def on_status(self, fn: Handler) -> Handler:
        return self.on("status", fn)

    def on_spectrum(self, fn: Handler) -> Handler:
        def wrapper(raw: dict[str, Any]) -> Any:
            return fn(parse_spectrum(raw))

        self._handlers.setdefault("spectrum", []).append(wrapper)
        return fn

    def on_heartbeat_updated(self, fn: Handler) -> Handler:
        return self.on("heartbeat.updated", fn)

    def on_inbox_updated(self, fn: Handler) -> Handler:
        return self.on("inbox.updated", fn)

    def on_tx_started(self, fn: Handler) -> Handler:
        return self.on("tx.started", fn)

    def on_tx_finished(self, fn: Handler) -> Handler:
        return self.on("tx.finished", fn)

    def on_radio_connected(self, fn: Handler) -> Handler:
        return self.on("radio.connected", fn)

    def on_radio_disconnected(self, fn: Handler) -> Handler:
        return self.on("radio.disconnected", fn)

    def on_config_changed(self, fn: Handler) -> Handler:
        return self.on("config.changed", fn)

    async def run_forever(self) -> None:
        """Block until the connection is closed."""
        if self._recv_task:
            try:
                await self._recv_task
            except asyncio.CancelledError:
                return

    async def get_status(self) -> Status:
        d = await self._cmd("status.get")
        self._status = parse_status(d)
        return self._status

    async def get_config(self) -> Config:
        d = await self._cmd("config.get")
        return parse_config(d)

    async def set_config(self, **kwargs: Any) -> Config:
        data = config_kwargs_to_api(kwargs)
        d = await self._cmd("config.set", data)
        return parse_config(d)

    async def get_audio_devices(self) -> AudioDevices:
        d = await self._cmd("audio.devices")
        return AudioDevices(
            inputs=list(d.get("input", [])),
            outputs=list(d.get("output", [])),
        )

    async def restart_audio(self) -> None:
        await self._cmd("audio.restart")

    async def get_radio(self) -> RadioStatus:
        d = await self._cmd("radio.get")
        return parse_radio_status(d)

    async def connect_rigctld(self, endpoint: str = "127.0.0.1:4532") -> RadioStatus:
        """Configure RIG_MODEL_NETRIGCTL (model=2, CAT PTT) and connect to a rigctld endpoint."""
        d = await self._cmd("radio.connect", {"rigctld": endpoint})
        return parse_radio_status(d)

    async def connect_radio(
        self,
        *,
        rigctld: str | None = None,
        rig_model: int | None = None,
        port: str | None = None,
        baud: int | None = None,
        ptt_type: int | None = None,
        data_bits: int | None = None,
        stop_bits: int | None = None,
        parity: int | None = None,
        handshake: int | None = None,
        dtr_state: int | None = None,
        rts_state: int | None = None,
    ) -> RadioStatus:
        data: dict[str, Any] = {}
        if rigctld is not None:
            data["rigctld"] = rigctld
        if rig_model is not None:
            data["rig_model"] = rig_model
        if port is not None:
            data["port"] = port
        if baud is not None:
            data["baud"] = baud
        if ptt_type is not None:
            data["ptt_type"] = ptt_type
        if data_bits is not None:
            data["data_bits"] = data_bits
        if stop_bits is not None:
            data["stop_bits"] = stop_bits
        if parity is not None:
            data["parity"] = parity
        if handshake is not None:
            data["handshake"] = handshake
        if dtr_state is not None:
            data["dtr_state"] = dtr_state
        if rts_state is not None:
            data["rts_state"] = rts_state
        reply_data = await self._cmd("radio.connect", data or None)
        radio_status = parse_radio_status(reply_data)
        return radio_status

    async def disconnect_radio(self) -> None:
        await self._cmd("radio.disconnect")

    async def set_frequency(self, khz: float) -> float:
        d = await self._cmd("radio.frequency.set", {"freq_khz": khz})
        return float(d.get("freq_khz", khz))

    async def set_ptt(self, on: bool) -> None:
        await self._cmd("radio.ptt.set", {"ptt": on})

    async def tune(self) -> None:
        await self._cmd("radio.tune")

    async def get_messages(self, offset: int = 0, limit: int = 100) -> list[DecodedMessage]:
        d = await self._cmd("messages.get", {"offset": offset, "limit": limit})
        return [parse_decoded_message(m) for m in d.get("messages", [])]

    async def clear_messages(self) -> None:
        await self._cmd("messages.clear")

    async def get_spectrum(self) -> Spectrum:
        d = await self._cmd("spectrum.get")
        return parse_spectrum(d)

    async def get_passband(self, *, clear_secs: int | None = None) -> PassbandState:
        """Return occupied 50 Hz passband bins within the clear-bin lookback window."""
        data = {"clear_secs": clear_secs} if clear_secs is not None else None
        d = await self._cmd("passband.get", data)
        return parse_passband_state(d)

    async def find_clear_freq(
        self,
        *,
        min_hz: float | None = None,
        max_hz: float | None = None,
        preferred_hz: float | None = None,
        clear_secs: int | None = None,
        avoid_hz: float | None = None,
        apply: bool = False,
    ) -> ClearFreqResult:
        """Find (and optionally apply) a clear TX audio offset over the lookback window."""
        data: dict[str, Any] = {"apply": apply}
        if min_hz is not None:
            data["min_hz"] = min_hz
        if max_hz is not None:
            data["max_hz"] = max_hz
        if preferred_hz is not None:
            data["preferred_hz"] = preferred_hz
        if clear_secs is not None:
            data["clear_secs"] = clear_secs
        if avoid_hz is not None:
            data["avoid_hz"] = avoid_hz
        d = await self._cmd("tx.find_clear", data)
        return parse_clear_freq_result(d)

    async def get_heartbeats(self) -> list[HeartbeatEntry]:
        """Return received @HB and HEARTBEAT SNR entries."""
        d = await self._cmd("heartbeats.get")
        return [parse_heartbeat_entry(h) for h in d.get("heartbeats", [])]

    async def clear_heartbeats(self) -> None:
        """Clear the in-memory heartbeat roster."""
        await self._cmd("heartbeats.clear")

    async def send(
        self,
        text: str,
        submode: str | int | None = None,
        *,
        tx_freq_hz: float | None = None,
    ) -> int:
        data: dict[str, Any] = {"text": text}
        if submode is not None:
            data["submode"] = str(submode)
        if tx_freq_hz is not None:
            data["tx_freq_hz"] = tx_freq_hz
        d = await self._cmd("tx.send", data)
        return int(d.get("queue_size", 0))

    async def send_heartbeat(self) -> int:
        d = await self._cmd("tx.hb")
        return int(d.get("queue_size", 0))

    async def send_heartbeat_ack(
        self,
        to: str,
        snr_db: int = 0,
        *,
        caller_freq_hz: float | None = None,
    ) -> ClearFreqResult:
        """Queue a 1-frame HEARTBEAT SNR acknowledgement on a clear audio bin."""
        data: dict[str, Any] = {"to": to.upper(), "snr_db": snr_db}
        if caller_freq_hz is not None:
            data["caller_freq_hz"] = caller_freq_hz
        d = await self._cmd("tx.hb_ack", data)
        return parse_clear_freq_result(d)

    async def send_snr_query(self, to: str) -> int:
        d = await self._cmd("tx.snr", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def send_info_query(self, to: str) -> int:
        d = await self._cmd("tx.info", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def send_status_query(self, to: str) -> int:
        d = await self._cmd("tx.status", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def get_tx_queue(self) -> list[TxFrame]:
        d = await self._cmd("tx.queue.get")
        return [parse_tx_frame(f) for f in d.get("queue", [])]

    async def clear_tx_queue(self) -> None:
        await self._cmd("tx.queue.clear")

    async def halt_tx(self) -> None:
        """Immediately halt in-progress audio TX, unkey PTT, and clear the TX queue."""
        await self._cmd("tx.halt")

    async def wait_for_tx(self, timeout: float | None = 120.0) -> None:
        done = asyncio.Event()

        def on_finished(_: Any) -> None:
            done.set()

        self.on("tx.finished", on_finished)
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        finally:
            self.off("tx.finished", on_finished)

    async def send_and_wait(
        self,
        text: str,
        submode: str | int | None = None,
        timeout: float = 120.0,
        *,
        tx_freq_hz: float | None = None,
    ) -> None:
        await self.send(text, submode=submode, tx_freq_hz=tx_freq_hz)
        await self.wait_for_tx(timeout=timeout)

    async def send_grid_query(self, to: str) -> int:
        d = await self._cmd("tx.grid", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def send_hearing_query(self, to: str) -> int:
        d = await self._cmd("tx.hearing", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def get_bands(self) -> list[BandEntry]:
        d = await self._cmd("bands.get")
        return [parse_band_entry(b) for b in d.get("bands", [])]

    async def set_bands(self, bands: list[BandEntry]) -> int:
        payload = [
            {"name": b.name, "freqKhz": b.freq_khz, "txFreqHz": b.tx_freq_hz}
            for b in bands
        ]
        d = await self._cmd("bands.set", {"bands": payload})
        return int(d.get("count", 0))

    async def get_version(self) -> VersionInfo:
        d = await self._cmd("version.get")
        return parse_version_info(d)

    async def get_qso_log(self, offset: int = 0, limit: int = 100) -> list[QsoEntry]:
        d = await self._cmd("qso.log.get", {"offset": offset, "limit": limit})
        return [parse_qso_entry(q) for q in d.get("qsos", [])]

    async def add_qso(
        self,
        callsign: str,
        *,
        grid: str = "",
        snr_db: int = 0,
        notes: str = "",
    ) -> int:
        d = await self._cmd(
            "qso.log.add",
            {"callsign": callsign.upper(), "grid": grid.upper(), "snr_db": snr_db, "notes": notes},
        )
        return int(d.get("total", 0))

    async def delete_qso(self, qso_id: int) -> bool:
        d = await self._cmd("qso.log.delete", {"id": qso_id})
        return bool(d.get("deleted", False))

    async def export_adif(self) -> str:
        d = await self._cmd("qso.log.adif")
        return str(d.get("adif", ""))

    async def get_inbox(self, for_call: str = "") -> list[InboxMessage]:
        data: dict[str, Any] = {}
        if for_call:
            data["for"] = for_call.upper()
        d = await self._cmd("inbox.get", data if data else None)
        return [parse_inbox_message(m) for m in d.get("messages", [])]

    async def inbox_send(self, to: str, body: str, *, via: str = "") -> bool:
        payload: dict[str, Any] = {"to": to.upper(), "body": body}
        via_clean = via.strip().upper()
        if via_clean:
            payload["via"] = via_clean
        d = await self._cmd("inbox.send", payload)
        return bool(d.get("queued", False))

    async def inbox_store(self, to: str, body: str) -> str:
        d = await self._cmd("inbox.store", {"to": to.upper(), "body": body})
        return str(d.get("id", ""))

    async def inbox_delete(self, msg_id: int) -> None:
        await self._cmd("inbox.delete", {"id": msg_id})

    async def inbox_mark_read(self, msg_id: int) -> None:
        await self._cmd("inbox.mark_read", {"id": msg_id})
