"""
jf8net — Python library for the JF8Call WebSocket API.

Quick start (async)::

    import asyncio
    from jf8net import DecodedMessage, JF8Client

    async def main():
        async with JF8Client() as client:
            status = await client.get_status()
            print(status)

            @client.on_message
            async def handle(msg: DecodedMessage):
                print(msg)

            await client.run_forever()

    asyncio.run(main())

Quick start (sync)::

    from jf8net.sync import JF8ClientSync

    with JF8ClientSync() as client:
        print(client.get_status())
        for msg in client.messages():
            print(msg)
"""

from ._client import ConnectionError, JF8Client, JF8Error
from ._models import (
    AudioDevices,
    BandEntry,
    ClearFreqResult,
    Config,
    DecodedMessage,
    FrameType,
    FrameUpdate,
    HeartbeatEntry,
    InboxMessage,
    MessageType,
    ModemType,
    PassbandSlot,
    PassbandState,
    PttType,
    QsoEntry,
    RadioStatus,
    Spectrum,
    Status,
    TxFrame,
    VersionInfo,
)

__version__ = "0.3.1"
__all__ = [
    "AudioDevices",
    "BandEntry",
    "ClearFreqResult",
    "Config",
    "ConnectionError",
    "DecodedMessage",
    "FrameType",
    "FrameUpdate",
    "HeartbeatEntry",
    "InboxMessage",
    "JF8Client",
    "JF8Error",
    "MessageType",
    "ModemType",
    "PassbandSlot",
    "PassbandState",
    "PttType",
    "QsoEntry",
    "RadioStatus",
    "Spectrum",
    "Status",
    "TxFrame",
    "VersionInfo",
]
