#!/usr/bin/env python3
"""02_receive_messages.py — Stream decoded messages and partial frame updates."""
import argparse
import asyncio

from jf8net import DecodedMessage, FrameUpdate, JF8Client, MessageType


async def main(host: str, port: int, show_frames: bool, only_call: str) -> None:
    async with JF8Client(host=host, port=port) as client:
        status = await client.get_status()
        my_call = status.callsign
        print(f"Connected. My callsign: {my_call or '(not set)'}")
        print(f"Listening on {status.frequency_khz} kHz  submode: {status.submode_name}")
        print("Press Ctrl-C to stop.\n")

        @client.on_message
        async def on_decoded(msg: DecodedMessage) -> None:
            if only_call and only_call.upper() not in (msg.from_call, msg.to):
                return
            prefix = ">>> " if msg.to == my_call else "    "
            type_tag = ""
            if msg.is_heartbeat:
                type_tag = " [HB]"
            elif msg.type == MessageType.SNR_REPLY:
                type_tag = " [SNR]"
            elif msg.type == MessageType.INFO_REPLY:
                type_tag = " [INFO]"
            elif msg.type == MessageType.STATUS_REPLY:
                type_tag = " [STATUS]"
            print(f"{prefix}{msg}{type_tag}")

        if show_frames:

            @client.on_frame
            async def on_frame(frame: FrameUpdate) -> None:
                print(
                    f"    [{frame.frame_type_name.upper():6s}] "
                    f"+{frame.freq_hz:.0f}Hz  {frame.assembled_text!r}"
                )

        try:
            await client.run_forever()
        except asyncio.CancelledError:
            return


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Stream decoded JF8Call messages")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)
    p.add_argument("--frames", action="store_true", help="Also show partial frame updates")
    p.add_argument("--callsign", default="", help="Only show messages from/to this callsign")
    parsed = p.parse_args()
    try:
        asyncio.run(main(parsed.host, parsed.port, parsed.frames, parsed.callsign))
    except KeyboardInterrupt:
        pass
