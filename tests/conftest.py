"""Ensure offline test runner works even when websockets is mocked or absent locally."""
from __future__ import annotations

import sys
import types

try:
    import websockets  # noqa: F401
except ModuleNotFoundError:
    ws_mod = types.ModuleType("websockets")
    exc_mod = types.ModuleType("websockets.exceptions")

    class WebSocketException(Exception):
        pass

    class ConnectionClosed(WebSocketException):
        def __init__(self, rcvd: object = None, sent: object = None) -> None:
            super().__init__("connection closed")
            self.rcvd = rcvd
            self.sent = sent

    async def _unconfigured_connect(_uri: str) -> object:
        raise OSError("unmocked connect")

    exc_mod.WebSocketException = WebSocketException  # type: ignore[attr-defined]
    exc_mod.ConnectionClosed = ConnectionClosed  # type: ignore[attr-defined]
    ws_mod.exceptions = exc_mod  # type: ignore[attr-defined]
    ws_mod.connect = _unconfigured_connect  # type: ignore[attr-defined]
    sys.modules["websockets"] = ws_mod
    sys.modules["websockets.exceptions"] = exc_mod
