import json
import asyncio
from typing import Optional
from collections import deque
from utils import parse_params
from traccar_client import TraccarClient

class DeviceService:
    def __init__(self, client: TraccarClient):
        self.client = client
        self.recent_event_ids = deque(maxlen=100)

    # -----------------------------------------------------------
    # SAVE ALLPARAMS (full parameter list)
    # -----------------------------------------------------------
    async def save_allparams(self, device_id: int, params: str):
        print(f"💾 Saving ALLPARAMS for device {device_id}")
        await self.client.update_device_attributes(device_id, {"baallparams": params})

    # -----------------------------------------------------------
    # Update based on PARAM SET (partial update)
    # -----------------------------------------------------------
    async def update_params(self, device_id: int, param_string: str):
        print(f"🔧 Incremental parameter update for device {device_id}")

        new_params = parse_params(param_string)

        dev = await self.client.get_device(device_id)
        attrs = dev.get("attributes", {})

        stored = attrs.get("baallparams", "")
        stored_dict = parse_params(stored)

        # merge
        stored_dict.update(new_params)

        # string format sorted by key
        merged = ";".join(f"{k}:{stored_dict[k]}" for k in sorted(stored_dict)) + ";"

        print(f"✅ Updated merged parameters for device {device_id}:")
        print(merged)

        await self.client.update_device_attributes(device_id, {"baallparams": merged})

    # -----------------------------------------------------------
    # Save TRACKERPARAMS (READ: Param ID:.... Value:...)
    # -----------------------------------------------------------
    async def save_trackerparams(self, device_id: int, params: str):
        print(f"💾 Saving TRACKERPARAMS (full) for device {device_id}")
        await self.client.update_device_attributes(device_id, {"trackerparams": params})

    # -----------------------------------------------------------
    # Update TRACKERPARAMS (WRITE: New value 2001:aaa;2002:bbb)
    # -----------------------------------------------------------
    async def update_trackerparams(self, device_id: int, param_string: str):
        print(f"🔧 Updating TRACKERPARAMS (partial) for device {device_id}")

        new_params = parse_params(param_string)

        dev = await self.client.get_device(device_id)
        attrs = dev.get("attributes", {})

        stored = attrs.get("trackerparams", "")
        stored_dict = parse_params(stored)

        stored_dict.update(new_params)

        merged = ";".join(f"{k}:{stored_dict[k]}" for k in sorted(stored_dict)) + ";"

        print(f"✅ Updated trackerparams for device {device_id}")
        print(merged)

        await self.client.update_device_attributes(device_id, {"trackerparams": merged})

    # -----------------------------------------------------------
    # WebSocket message parser
    # -----------------------------------------------------------
    def handle_ws_message(self, msg: str):
        try:
            data = json.loads(msg)

            if "events" not in data:
                return

            # print(f"\n📨 WS Message: {len(data['events'])} events")

            for event in data["events"]:
                attrs = event.get("attributes", {})
                result = attrs.get("result")
                if not result:
                    continue

                device_id = event.get("deviceId")
                event_id = event.get("id")

                if event_id and event_id in self.recent_event_ids:
                    #print(f"   🛑 Skipping duplicate event {event_id}")
                    continue
                if event_id:
                    self.recent_event_ids.append(event_id)

                print(f"✅ Event {event_id} → Device {device_id}")
                print(result)

                # Full parameter list
                if result.startswith("ALLPARAMS:"):
                    params = result[len("ALLPARAMS:"):]
                    asyncio.create_task(self.save_allparams(device_id, params))
                    continue

                # Partial update
                if result.startswith("PARAM SET:"):
                    params = result[len("PARAM SET:"):]
                    asyncio.create_task(self.update_params(device_id, params))
                    continue

                # READ PARAMS (Param ID:17703 Value:0;17603:0;...)
                if result.startswith("Param ID:"):
                    try:
                        # split into header and tail by 'Value:'
                        parts = result.split("Value:", 1)
                        header = parts[0].strip()  # e.g. "Param ID:17703"
                        tail = parts[1].strip() if len(parts) > 1 else ""

                        # extract id number from header
                        # header format expected "Param ID:17703" (may have spaces)
                        id_part = header.replace("Param ID:", "").strip()
                        # first value is before first ';' in tail (or whole tail if no ;)
                        if ";" in tail:
                            first_value, rest = tail.split(";", 1)
                            rest = rest.strip()
                        else:
                            first_value = tail
                            rest = ""

                        first_value = first_value.strip()
                        # construct final params: "17703:0;rest..."
                        final_params = f"{id_part}:{first_value}"
                        if rest:
                            final_params = final_params + ";" + rest

                        # schedule save of trackerparams (this message is partial)
                        asyncio.create_task(self.save_trackerparams(device_id, final_params))
                    except Exception as e:
                        print("❌ Param-ID parse error:", e, " | raw:", result)
                    continue

                # NEW VALUE (WRITE)
                if result.startswith("New value"):
                    params = result[len("New value"):].strip()
                    asyncio.create_task(self.update_trackerparams(device_id, params))
                    continue

        except Exception as e:
            print("❌ WS parse error:", e)
