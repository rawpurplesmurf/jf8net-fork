#!/usr/bin/env python3
"""05_radio_control.py — Radio and ATU control via the API."""
import argparse
import asyncio

from jf8net import JF8Client

JS8_CALLING = {
    10: 28078.0,
    12: 24922.0,
    15: 21078.0,
    17: 18104.0,
    20: 14078.0,
    30: 10130.0,
    40: 7078.0,
    60: 5357.0,
    80: 3578.0,
    160: 1842.0,
}


async def main(host: str, port: int, args: argparse.Namespace) -> None:
    async with JF8Client(host=host, port=port) as client:
        radio = await client.get_radio()
        config = await client.get_config()

        if args.connect:
            print(f"Connecting to rig (model={args.model}, port={args.port_dev})...")
            await client.connect_radio(
                rig_model=args.model,
                port=args.port_dev,
                baud=args.baud,
                ptt_type=args.ptt,
            )
            await asyncio.sleep(1)
            print(await client.get_radio())
            return

        if args.disconnect:
            await client.disconnect_radio()
            print("Disconnected from rig.")
            return

        if not radio.connected:
            print("Rig not connected. Use --connect first.")
            return

        target_khz = None
        if args.band:
            target_khz = JS8_CALLING.get(args.band)
            if target_khz is None:
                print(f"Unknown band: {args.band}m. Known bands: {sorted(JS8_CALLING)}")
                return
            print(f"JS8 calling frequency for {args.band}m: {target_khz} kHz")
        elif args.freq:
            target_khz = args.freq

        if target_khz:
            print(f"Setting frequency to {target_khz} kHz...")
            actual = await client.set_frequency(target_khz)
            print(f"VFO set to {actual} kHz")

            if args.tune or config.auto_atu:
                if config.auto_atu:
                    print("(auto_atu is enabled — ATU was triggered automatically)")
                else:
                    print("Triggering ATU tune cycle (RIG_OP_TUNE, no RF)...")
                    await client.tune()
                    print("ATU tune sent.")

        radio = await client.get_radio()
        print("\nCurrent radio state:")
        print(radio)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="JF8Call radio control")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102, dest="port")
    p.add_argument("--freq", type=float, metavar="KHZ", help="Set VFO frequency in kHz")
    p.add_argument("--band", type=int, metavar="M", help="Tune to JS8 calling frequency")
    p.add_argument("--tune", action="store_true", help="Trigger ATU tune cycle")
    p.add_argument("--connect", action="store_true", help="Connect to rig")
    p.add_argument("--model", type=int, default=None, help="Hamlib model number")
    p.add_argument("--port-dev", metavar="PATH", default=None, help="Serial or TCP port")
    p.add_argument("--baud", type=int, default=None, help="Baud rate")
    p.add_argument("--ptt", type=int, default=None, help="PTT type: 0=VOX 1=CAT 2=DTR 3=RTS")
    p.add_argument("--disconnect", action="store_true", help="Disconnect from rig")
    parsed = p.parse_args()
    asyncio.run(main(parsed.host, parsed.port, parsed))
