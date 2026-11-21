"""
jf8net.sync — Synchronous wrapper around JF8Client.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from ._client import ConnectionError, JF8Client, JF8Error
from ._models import (
    AudioDevices,
    BandEntry,
    ClearFreqResult,
    Config,
    DecodedMessage,
    FrameUpdate,
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

__all__ = ["ConnectionError", "JF8ClientSync", "JF8Error"]

logger = logging.getLogger(__name__)


class JF8ClientSync:
    """Synchronous wrapper around :class:`~jf8net.JF8Client`."""

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
        self._async = JF8Client(
            host,
            port,
            tls=tls,
            auto_reconnect=auto_reconnect,
            reconnect_delay=reconnect_delay,
            cmd_timeout=cmd_timeout,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._connect_err: BaseException | None = None

    def connect(self) -> None:
        """Open the connection. Called automatically by the context manager."""
        self._ready.clear()
        self._connect_err = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="jf8net-sync",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=15.0):
            raise ConnectionError("Timed out waiting for JF8Call connection")
        if self._connect_err is not None:
            raise ConnectionError(str(self._connect_err)) from self._connect_err

    def disconnect(self) -> None:
        """Close the connection."""
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._async.disconnect(),
                self._loop,
            ).result(timeout=5.0)
            try:
                if not self._loop.is_closed():
                    self._loop.call_soon_threadsafe(self._loop.stop)
            except RuntimeError:
                logger.debug("Sync event loop already closed during disconnect")
        if self._thread:
            self._thread.join(timeout=5.0)

    def _run_loop(self) -> None:
        if self._loop is None:
            return
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start())
        finally:
            self._loop.close()

    async def _start(self) -> None:
        try:
            await self._async.connect()
        except (OSError, ValueError, JF8Error) as exc:
            self._connect_err = exc
            self._ready.set()
            return
        self._ready.set()
        await self._async.run_forever()

    def __enter__(self) -> JF8ClientSync:  # noqa: PYI034
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    def _run(self, coro: Any) -> Any:
        if self._loop is None or self._loop.is_closed():
            raise ConnectionError("Not connected")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=self._async._cmd_timeout + 2)

    def on(self, event: str, handler: Callable[..., Any] | None = None) -> Any:
        return self._async.on(event, handler)

    def off(self, event: str, handler: Callable[..., Any]) -> None:
        self._async.off(event, handler)

    def on_message(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_message(fn)

    def on_frame(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_frame(fn)

    def on_status(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_status(fn)

    def on_spectrum(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_spectrum(fn)

    def on_heartbeat_updated(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_heartbeat_updated(fn)

    def on_inbox_updated(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_inbox_updated(fn)

    def on_tx_started(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_tx_started(fn)

    def on_tx_finished(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_tx_finished(fn)

    def on_radio_connected(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_radio_connected(fn)

    def on_radio_disconnected(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_radio_disconnected(fn)

    def on_config_changed(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        return self._async.on_config_changed(fn)

    def run_forever(self) -> None:
        if self._thread:
            self._thread.join()

    @property
    def cached_status(self) -> Status | None:
        return self._async.cached_status

    def get_status(self) -> Status:
        return self._run(self._async.get_status())

    def get_config(self) -> Config:
        return self._run(self._async.get_config())

    def set_config(self, **kwargs: Any) -> Config:
        return self._run(self._async.set_config(**kwargs))

    def get_audio_devices(self) -> AudioDevices:
        return self._run(self._async.get_audio_devices())

    def restart_audio(self) -> None:
        self._run(self._async.restart_audio())

    def get_radio(self) -> RadioStatus:
        return self._run(self._async.get_radio())

    def connect_rigctld(self, endpoint: str = "127.0.0.1:4532") -> RadioStatus:
        return self._run(self._async.connect_rigctld(endpoint))

    def connect_radio(self, **kwargs: Any) -> RadioStatus:
        return self._run(self._async.connect_radio(**kwargs))

    def disconnect_radio(self) -> None:
        self._run(self._async.disconnect_radio())

    def set_frequency(self, khz: float) -> float:
        return self._run(self._async.set_frequency(khz))

    def set_ptt(self, on: bool) -> None:
        self._run(self._async.set_ptt(on))

    def tune(self) -> None:
        self._run(self._async.tune())

    def get_messages(self, offset: int = 0, limit: int = 100) -> list[DecodedMessage]:
        return self._run(self._async.get_messages(offset, limit))

    def clear_messages(self) -> None:
        self._run(self._async.clear_messages())

    def get_spectrum(self) -> Spectrum:
        return self._run(self._async.get_spectrum())

    def get_passband(self, *, clear_secs: int | None = None) -> PassbandState:
        return self._run(self._async.get_passband(clear_secs=clear_secs))

    def find_clear_freq(self, **kwargs: Any) -> ClearFreqResult:
        return self._run(self._async.find_clear_freq(**kwargs))

    def get_heartbeats(self) -> list[HeartbeatEntry]:
        return self._run(self._async.get_heartbeats())

    def clear_heartbeats(self) -> None:
        self._run(self._async.clear_heartbeats())

    def send(
        self,
        text: str,
        submode: str | int | None = None,
        *,
        tx_freq_hz: float | None = None,
    ) -> int:
        return self._run(self._async.send(text, submode=submode, tx_freq_hz=tx_freq_hz))

    def send_heartbeat(self) -> int:
        return self._run(self._async.send_heartbeat())

    def send_heartbeat_ack(
        self,
        to: str,
        snr_db: int = 0,
        *,
        caller_freq_hz: float | None = None,
    ) -> ClearFreqResult:
        return self._run(
            self._async.send_heartbeat_ack(to, snr_db, caller_freq_hz=caller_freq_hz)
        )

    def send_snr_query(self, to: str) -> int:
        return self._run(self._async.send_snr_query(to))

    def send_info_query(self, to: str) -> int:
        return self._run(self._async.send_info_query(to))

    def send_status_query(self, to: str) -> int:
        return self._run(self._async.send_status_query(to))

    def get_tx_queue(self) -> list[TxFrame]:
        return self._run(self._async.get_tx_queue())

    def clear_tx_queue(self) -> None:
        """Clear pending frames from the JF8Call TX queue."""
        self._run(self._async.clear_tx_queue())

    def halt_tx(self) -> None:
        """Immediately halt in-progress audio TX, unkey PTT, and clear the TX queue."""
        self._run(self._async.halt_tx())

    def wait_for_tx(self, timeout: float = 120.0) -> None:
        self._run(self._async.wait_for_tx(timeout=timeout))

    def send_and_wait(
        self,
        text: str,
        submode: str | int | None = None,
        timeout: float = 120.0,
        *,
        tx_freq_hz: float | None = None,
    ) -> None:
        self._run(
            self._async.send_and_wait(
                text,
                submode=submode,
                timeout=timeout,
                tx_freq_hz=tx_freq_hz,
            )
        )

    def send_grid_query(self, to: str) -> int:
        return self._run(self._async.send_grid_query(to))

    def send_hearing_query(self, to: str) -> int:
        return self._run(self._async.send_hearing_query(to))

    def get_bands(self) -> list[BandEntry]:
        return self._run(self._async.get_bands())

    def set_bands(self, bands: list[BandEntry]) -> int:
        return self._run(self._async.set_bands(bands))

    def get_version(self) -> VersionInfo:
        return self._run(self._async.get_version())

    def get_qso_log(self, offset: int = 0, limit: int = 100) -> list[QsoEntry]:
        return self._run(self._async.get_qso_log(offset=offset, limit=limit))

    def add_qso(
        self,
        callsign: str,
        *,
        grid: str = "",
        snr_db: int = 0,
        notes: str = "",
    ) -> int:
        return self._run(
            self._async.add_qso(callsign, grid=grid, snr_db=snr_db, notes=notes)
        )

    def delete_qso(self, qso_id: int) -> bool:
        return self._run(self._async.delete_qso(qso_id))

    def export_adif(self) -> str:
        return self._run(self._async.export_adif())

    def get_inbox(self, for_call: str = "") -> list[InboxMessage]:
        return self._run(self._async.get_inbox(for_call=for_call))

    def inbox_send(self, to: str, body: str, *, via: str = "") -> bool:
        return self._run(self._async.inbox_send(to, body, via=via))

    def inbox_store(self, to: str, body: str) -> str:
        return self._run(self._async.inbox_store(to, body))

    def inbox_delete(self, msg_id: int) -> None:
        self._run(self._async.inbox_delete(msg_id))

    def inbox_mark_read(self, msg_id: int) -> None:
        self._run(self._async.inbox_mark_read(msg_id))

    def messages(
        self,
        *,
        include_frames: bool = False,
        timeout: float | None = None,
    ) -> Iterator[DecodedMessage | FrameUpdate]:
        q: queue.Queue[DecodedMessage | FrameUpdate] = queue.Queue()

        def on_decoded(msg: DecodedMessage) -> None:
            q.put(msg)

        def on_frame(frame: FrameUpdate) -> None:
            q.put(frame)

        self._async.on("message.decoded", on_decoded)
        if include_frames:
            self._async.on("message.frame", on_frame)

        try:
            while True:
                try:
                    yield q.get(timeout=timeout)
                except queue.Empty:
                    return
        finally:
            self._async.off("message.decoded", on_decoded)
            if include_frames:
                self._async.off("message.frame", on_frame)
