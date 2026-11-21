#!/usr/bin/env python3
"""04_frame_assembly.py — Real-time multi-frame message assembly display."""
import argparse
import asyncio
import time
from typing import Any

from jf8net import DecodedMessage, FrameType, FrameUpdate, JF8Client

assembly: dict[int, dict[str, Any]] = {}


async def main(host: str, port: int) -> None:
    async with JF8Client(host=host, port=port) as client:
        status = await client.get_status()
        print(f"Connected. Listening on {status.frequency_khz} kHz\n")
        print("Watching for multi-frame GFSK8 messages. Press Ctrl-C to stop.\n")

        @client.on_frame
        def on_frame(frame: FrameUpdate) -> None:
            key = frame.freq_key
            now = time.time()

            if frame.frame_type == FrameType.FIRST:
                assembly[key] = {
                    "start": now,
                    "freq_hz": frame.freq_hz,
                    "snr_db": frame.snr_db,
                    "submode_name": frame.submode_name,
                }
                t = frame.time.strftime("%H:%M:%S")
                print(
                    f"[{t}] +{frame.freq_hz:.0f}Hz SNR{frame.snr_db:+d}"
                    f"  {frame.submode_name}  <- FIRST FRAME"
                )
                print(f"       Text so far: {frame.assembled_text!r}")
            elif frame.frame_type == FrameType.MIDDLE:
                elapsed = now - float(assembly.get(key, {}).get("start", now))
                t = frame.time.strftime("%H:%M:%S")
                print(f"[{t}] +{frame.freq_hz:.0f}Hz  <- CONTINUATION ({elapsed:.0f}s in)")
                print(f"       Text so far: {frame.assembled_text!r}")

        @client.on_message
        def on_complete(msg: DecodedMessage) -> None:
            key = msg.freq_key
            info = assembly.pop(key, {})
            elapsed = time.time() - float(info.get("start", time.time()))
            t = msg.time.strftime("%H:%M:%S")
            if info:
                print(
                    f"[{t}] +{msg.freq_hz:.0f}Hz  <- COMPLETE ({elapsed:.0f}s, {msg.submode_name})"
                )
            else:
                print(
                    f"[{t}] +{msg.freq_hz:.0f}Hz SNR{msg.snr_db:+d}"
                    f"  {msg.submode_name}  [single frame]"
                )
            print(f"       {msg.from_call} -> {msg.to or '*'}: {msg.body}\n")

        try:
            await client.run_forever()
        except asyncio.CancelledError:
            return


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Show GFSK8 multi-frame assembly in real time")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)
    parsed = p.parse_args()
    try:
        asyncio.run(main(parsed.host, parsed.port))
    except KeyboardInterrupt:
        pass
