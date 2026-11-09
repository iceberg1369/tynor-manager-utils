"""One-off: run the registration setup (ensure_tynor_attributes) over every
existing device, limited to the filter keys by default.

Registration links the TYNOR computed attributes only to devices it registers,
so devices registered before a key was added never get it. The default set is
TYNOR_SKIP_ATTRIBUTES (eventKey, resultKey, stopKey): they only let records past
traccar's filters. alarm/valid/ignition are left out on purpose, because linking
alarm fleet-wide starts new alarm notifications for every customer.

    python sweep_tynor_attributes.py                 # dry run: print what would change
    python sweep_tynor_attributes.py --apply         # do it
    python sweep_tynor_attributes.py --apply --device 266 --names stopKey
"""
import argparse
import asyncio
import collections

import config
from services import ensure_tynor_attributes, TYNOR_SKIP_ATTRIBUTES, TYNOR_COMPUTED_ATTRIBUTES
from traccar_client import TraccarClient


class DryRunClient:
    """Passes reads through to traccar and records the writes instead of sending them."""

    def __init__(self, client):
        self._client = client
        self.writes = []

    def __getattr__(self, name):
        return getattr(self._client, name)

    async def add_permission_generic(self, *args):
        self.writes.append(("link", args))
        return True

    async def update_device_attributes(self, device_id, new_attrs, model=None):
        self.writes.append(("attrs", (device_id, new_attrs)))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    parser.add_argument("--names", nargs="+", default=TYNOR_SKIP_ATTRIBUTES,
                        choices=[a["attribute"] for a in TYNOR_COMPUTED_ATTRIBUTES])
    parser.add_argument("--device", type=int, nargs="+", help="only these device ids")
    args = parser.parse_args()

    traccar = TraccarClient(config.BASE_URL, config.TOKEN, verify_ssl=False)
    try:
        devices = await traccar.get_devices()
        if args.device:
            devices = [d for d in devices if d["id"] in args.device]
        print(f"{'APPLY' if args.apply else 'DRY RUN'}: {', '.join(args.names)} on {len(devices)} devices")
        summary = collections.Counter()
        for device in sorted(devices, key=lambda d: d["id"]):
            client = traccar if args.apply else DryRunClient(traccar)
            try:
                await ensure_tynor_attributes(client, device["id"], names=args.names)
            except Exception as error:
                summary["failed"] += 1
                print(f"❌ device {device['id']}: {error!r}")
                continue
            if not args.apply:
                for kind, detail in client.writes:
                    summary[kind] += 1
                    print(f"   would {kind} device {device['id']}: {detail}")
            summary["done"] += 1
        print(f"Summary: {dict(summary)}")
    finally:
        await traccar.close()


if __name__ == "__main__":
    asyncio.run(main())
