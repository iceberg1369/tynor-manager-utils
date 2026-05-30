import json
import re
import asyncio
from typing import Optional
from collections import deque
from utils import parse_params
from datetime import datetime
from utils import parse_params
from traccar_client import TraccarClient

# Helper function for device type mapping
def device_type_to_model(device_type):
    dt = int(device_type)
    if dt == 170: return "develope_device"
    if dt == 120: return "TYNOR-T120"
    if dt == 90: return "TYNOR-T900"
    if dt == 95: return "TYNOR-T950"
    if dt == 92: return "TYNOR-T920"
    return "unknown"

class DeviceService:
    def __init__(self, client: TraccarClient):
        self.client = client
        self.recent_event_ids = deque(maxlen=100)
        self.device_names = {}
        self.known_device_ids: set = set()

    async def load_known_devices(self):
        """Pre-fetch the current device list so we can detect newly added ones later."""
        devices = await self.client.get_devices()
        self.known_device_ids = {d["id"] for d in devices if d.get("id")}
        print(f"✅ Pre-fetched {len(self.known_device_ids)} known devices.")

    # -----------------------------------------------------------
    # Handle a device coming online — detect newly added devices
    # -----------------------------------------------------------
    async def _handle_device_online(self, device_id: int):
        if not device_id or device_id in self.known_device_ids:
            return
        self.known_device_ids.add(device_id)
        try:
            dev = await self.client.get_device(device_id)
        except Exception as e:
            print(f"❌ Failed to fetch new device {device_id}: {e}")
            return

        print(f"\n🆕 New device detected — ID:{device_id}")
        print(dev)

        # Kick off the new-device provisioning sequence. It starts by asking the
        # device for its firmware/model (getver) after a 2-minute settle delay.
        asyncio.create_task(self._provision_new_device(device_id))

    # -----------------------------------------------------------
    # New-device provisioning sequence
    # -----------------------------------------------------------
    async def _provision_new_device(self, device_id: int, delay: int = 120):
        """Wait for the device to settle, then request its version.

        The `getver` response (handled in `handle_version_response`) drives the
        rest of the command sequence.
        """
        await asyncio.sleep(delay)
        try:
            await self.client.send_command(device_id, "getver")
            print(f"📦 Sent getver to new device {device_id} (after {delay}s)")
        except Exception as e:
            print(f"❌ Failed to send getver to {device_id}: {e}")

    # -----------------------------------------------------------
    # Handle getver response: "VERSION:2.1.0d MODEL:50/2"
    # -----------------------------------------------------------
    async def handle_version_response(self, device_id: int, result: str):
        m = re.search(r"VERSION:\s*(\S+)\s+MODEL:\s*(\S+)", result)
        if not m:
            print(f"⚠️ Could not parse getver response for {device_id}: {result!r}")
            return

        version, model = m.group(1), m.group(2)
        print(f"🔖 Device {device_id} version={version} model={model}")

        await self.client.update_device_attributes(
            device_id, {"firmware": version, "hw_model": model}
        )

        # If we don't yet have the SIM's IMSI on file, ask the device for it.
        dev = await self.client.get_device(device_id)
        imsi = str(dev.get("attributes", {}).get("imsi", "")).strip()
        if not imsi:
            try:
                await self.client.send_command(device_id, "getimsi")
                print(f"📨 No IMSI on file — sent getimsi to device {device_id}")
            except Exception as e:
                print(f"❌ Failed to send getimsi to {device_id}: {e}")
        else:
            print(f"⏭️ IMSI already known for device {device_id} ({imsi}) — running SIM provisioning")
            # IMSI is on file, so run the SIM-card discovery steps for this device:
            # request the SIMCARD No (if missing) and a balance check.
            from tasks import simcard_no_check_for_device, sim_balance_qssd_for_device
            try:
                await simcard_no_check_for_device(self.client, dev)
            except Exception as e:
                print(f"❌ simcard_no_check failed for {device_id}: {e}")
            try:
                await sim_balance_qssd_for_device(self.client, dev)
            except Exception as e:
                print(f"❌ sim_balance_qssd failed for {device_id}: {e}")

        # TODO: continue the provisioning command sequence here.

    async def get_device_name(self, device_id: int):
        if not device_id:
            return ""

        if device_id in self.device_names:
            return self.device_names[device_id]

        try:
            dev = await self.client.get_device(device_id)
            name = dev.get("name", "")
            self.device_names[device_id] = name
            return name
        except Exception as e:
            print(f"⚠️ Could not fetch name for device {device_id}: {e}")
            return ""

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

        await self.client.update_device_attributes(device_id, {"trackerparams": merged})

    # -----------------------------------------------------------
    # Update IMSI
    # -----------------------------------------------------------
    async def update_imsi(self, device_id: int, imsi: str):
        dev = await self.client.get_device(device_id)
        attrs = dev.get("attributes", {})
        current_imsi = str(attrs.get("imsi", "")).strip()
        new_imsi = str(imsi).strip()

        if current_imsi == new_imsi:
            print(f"⏭️ IMSI unchanged for device {device_id}, skipping update.")
            return

        # IMSI changed => clear SIMCARD No so it can be re-discovered.
        for key in ("SIMCARD No", "simcard_no", "simcardNo", "simcard"):
            attrs.pop(key, None)
        attrs["imsi"] = new_imsi

        print(f"💾 Saving IMSI {new_imsi} for device {device_id} (was: {current_imsi or 'empty'})")
        payload = {
            "id": device_id,
            "name": dev["name"],
            "uniqueId": dev["uniqueId"],
            "status": dev.get("status"),
            "model": dev.get("model"),
            "groupId": dev.get("groupId"),
            "contact": dev.get("contact"),
            "category": dev.get("category"),
            "attributes": attrs,
        }
        await self.client.update_device(device_id, payload)

        # IMSI just changed (SIMCARD No was cleared above), so kick off SIM-card
        # discovery right away: request the SIMCARD No and a balance check.
        # `dev["attributes"]` is `attrs`, which already reflects the new IMSI and
        # the cleared SIMCARD No, so the helpers act on fresh state.
        from tasks import simcard_no_check_for_device, sim_balance_qssd_for_device
        try:
            await simcard_no_check_for_device(self.client, dev)
        except Exception as e:
            print(f"❌ simcard_no_check failed for {device_id}: {e}")
        try:
            await sim_balance_qssd_for_device(self.client, dev)
        except Exception as e:
            print(f"❌ sim_balance_qssd failed for {device_id}: {e}")

    # -----------------------------------------------------------
    # Generate Device Name (Python port of PHP logic)
    # -----------------------------------------------------------
    async def generate_device_name(self, user_id: int):
        devices = await self.client.get_devices({"userId": user_id})
        
        last_device_id = 0
        last_device_name = ""
        
        for item in devices:
            name = item.get("name", "")
            # Check if name starts with "خودرو"
            # PHP: explode(" ", $item->name)[0] == "خودرو"
            parts = name.split(" ")
            if len(parts) > 0 and parts[0] == "خودرو":
                if item["id"] > last_device_id:
                    last_device_id = item["id"]
                    last_device_name = name
                    
        if last_device_name:
            parts = last_device_name.split(" ")
            if len(parts) > 1 and parts[0] == "خودرو":
                try:
                    num = int(parts[1])
                    return f"{parts[0]} {num + 1}"
                except ValueError:
                    return "خودرو 1"
            else:
                 return "خودرو 1"
        else:
            return "خودرو 1"

    # -----------------------------------------------------------
    # Handle Registration Event (CMD 29)
    # -----------------------------------------------------------
    async def handle_registration_event(self, device_id: int, command_result: dict):
        try:
            print(f"🆕 Handling Registration/Init for Device {device_id}")
            
            param = command_result.get("param", {})
            
            imei = param.get("imei")
            imsi = param.get("imsi")
            spn = param.get("spn")
            fw = param.get("fw")
            device_password = param.get("dp")
            device_type = param.get("dm")
            hardware_revision = param.get("dr")
            ts = param.get("ts")
            owner = param.get("owner")
            
            # Format date
            if ts:
                reg_date = datetime.fromtimestamp(ts).strftime('%m/%d/%Y %H:%M:%S')
            else:
                 reg_date = datetime.now().strftime('%m/%d/%Y %H:%M:%S')

            # Get current device details
            dev = await self.client.get_device(device_id)
            attrs = dev.get("attributes", {})
            
            # Get User ID (Assignee)
            user_id = attrs.get("assignee")
            if not user_id:
                print(f"⚠️ Device {device_id} has no assignee (user_id). Skipping specific naming.")
                # We might still proceed with updating other attributes? 
                # PHP code uses user_id to generate name. If missing, maybe just skip naming?
                # User provided code: $user_id = $device->attributes->assignee;
                # If null, generateDeviceName might fail or return default?
                # Let's assume user_id is zero if missing?
                user_id = 0 
                
            # Generate Name
            if user_id:
                 new_name = await self.generate_device_name(user_id)
            else:
                 new_name = f"Device {device_id}" # Fallback
            
            # Map Model
            new_model = device_type_to_model(device_type) if device_type else dev.get("model")
            
            # Update Attributes
            if "registrationDate" not in attrs:
                attrs["registrationDate"] = reg_date
            attrs["imsi"] = imsi
            attrs["spn"] = spn
            attrs["firmware"] = fw
            attrs["hw_rev"] = hardware_revision
            attrs["Device Password"] = device_password
            
            # Prepare update payload
            # We want to update name, model, and attributes.
            device_update = {
                "id": device_id,
                "name": new_name,
                "uniqueId": dev["uniqueId"], # Required usually
                "model": new_model,
                "attributes": attrs,
                "groupId": dev.get("groupId"),
                "phone": dev.get("phone"),
                "category": dev.get("category"),
                "disabled": dev.get("disabled", False)
            }
            
            await self.client.update_device(device_id, device_update)
            self.device_names[device_id] = new_name
            print(f"✅ Device {device_id} initialized with Name: {new_name}, Model: {new_model}")

        except Exception as e:
            print(f"❌ Registration Handler Error: {e}")

    async def handle_ws_message(self, msg: str):
        try:
            data = json.loads(msg)

            positions = data.get("positions", [])
            # if positions:
            #     print(f"📍 WS positions batch received: {len(positions)}")

            for device in data.get("devices", []):
                device_id = device.get("id")
                device_name = device.get("name", "")
                if device_id:
                    self.device_names[device_id] = device_name

            if "events" not in data:
                return

            # print(f"\n📨 WS Message: {len(data['events'])} events")

            for event in data["events"]:
                device_id = event.get("deviceId")
                event_id = event.get("id")
                event_type = event.get("type")

                if event_type == "deviceOnline":
                    asyncio.create_task(self._handle_device_online(device_id))
                    continue

                attrs = event.get("attributes", {})
                result = attrs.get("result")
                if not result:
                    continue

                if event_id and event_id in self.recent_event_ids:
                    #print(f"   🛑 Skipping duplicate event {event_id}")
                    continue
                if event_id:
                    self.recent_event_ids.append(event_id)

                device_name = await self.get_device_name(device_id)
                print(f"✅ Event ID:{event_id} → Device ID:{device_id}  Name:{device_name}")
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

                # VERSION RESPONSE (getver): "VERSION:2.1.0d MODEL:50/2"
                if result.startswith("VERSION:"):
                    asyncio.create_task(self.handle_version_response(device_id, result))
                    continue

                # IMSI RESPONSE
                if result.startswith("IMSI:"):
                    imsi = result.split(":", 1)[1].strip()
                    if imsi.isdigit():
                        asyncio.create_task(self.update_imsi(device_id, imsi))
                    continue

                # Device password response
                if result.startswith("PASS:"):
                    device_password = result.split(":", 1)[1].strip()
                    if device_password:
                        asyncio.create_task(
                            self.client.update_device_attributes(
                                device_id, {"Device Password": device_password}
                            )
                        )
                    continue

                if result.startswith("{\"cmd\":29"):
                    print("Got 29 command response")
                    try:
                        cmd_res = json.loads(result)
                        if cmd_res.get("cmd") == 29:
                            asyncio.create_task(self.handle_registration_event(device_id, cmd_res))
                    except Exception as e:
                        print(f"❌ Failed to parse Cmd 29 JSON: {e}")

        except Exception as e:
            print("❌ WS parse error:", e)
