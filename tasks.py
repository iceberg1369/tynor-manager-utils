# tasks.py
import asyncio
from traccar_client import TraccarClient

# -----------------------------------------------------------
# Periodic Task: Send qssd every 6 hours
# -----------------------------------------------------------
async def periodic_qssd_task(api_client: TraccarClient):
    while True:
        try:
            print("\n⏰ Executing periodic QSSD command task...")
            # Re-fetch devices to get fresh status
            devices = await api_client.get_devices()

            t950_devices = [
                d for d in devices
                if (d.get("model") == "T950" or d.get("attributes", {}).get("model") == "T950") and d.get("id") == 115
            ]

            count = 0
            for dev in t950_devices:
                if dev.get("status") == "online":
                    dev_id = dev["id"]
                    try:
                        await api_client.send_command(dev_id, "qssd:*140*11#")
                        print(f"   -> Sent qssd to {dev_id}")
                        count += 1
                    except Exception as e:
                        print(f"   -> Failed to send to {dev_id}: {e}")
            
            print(f"✅ Periodic task: Sent to {count} online devices.")

        except Exception as e:
            print(f"❌ Periodic task top-level error: {e}")

        # Wait 6 hours
        await asyncio.sleep(6 * 3600)



# -----------------------------------------------------------
# Periodic Task: getparams every 6 hours
# -----------------------------------------------------------
async def periodic_getparams_task(api_client: TraccarClient):
    while True:
        try:
            print("\n⏰ Executing periodic get params task...")
            # Re-fetch devices to get fresh status
            devices = await api_client.get_devices()

            t950_devices = [
                d for d in devices
                if (d.get("model") == "T950" or d.get("attributes", {}).get("model") == "T950") and d.get("id") == 115
            ]

            count = 0
            for dev in t950_devices:
                if dev.get("status") == "online":
                    dev_id = dev["id"]
                    try:
                        await api_client.send_command(dev_id, "getparam 17703;17603;7036;11503;7032;7033;21605;17607;7035;21604;11604;11104;11205;21610;18300;18301;18302;18303;18304;18305;18306;18307;18308;13809")
                        print(f"   -> Sent getparam to {dev_id}")
                        count += 1
                    except Exception as e:
                        print(f"   -> Failed to send to {dev_id}: {e}")
            
            print(f"✅ Periodic task: Sent to {count} online devices.")

        except Exception as e:
            print(f"❌ Periodic task top-level error: {e}")

        # Wait 6 hours
        await asyncio.sleep(6 * 3600)
