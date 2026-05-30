
import asyncio
import re
import uvicorn
import os
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import config
from traccar_client import TraccarClient
from services import DeviceService
from tasks import periodic_sim_balance_qssd_task
from tasks import periodic_simcard_no_task
from tasks import periodic_getparams_task
from tasks import periodic_getimsi_task
from tasks import periodic_getpass_task
from database import init_db
from api.fota import router as fota_router
from api.ussd_parser import router as ussd_router
from api.auth import router as auth_router
from api.device import router as device_router
import ftp_server

# Global reference to client for the route handler to use
# Ideally we would use dependency injection in FastAPI but a global is fine for this simple port to match original logic
client: Optional[TraccarClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    global client
    
    # Initialize Database
    init_db()
    
    # Old FTP instances are now killed by the FTP server script itself on startup

    client = TraccarClient(config.BASE_URL, config.TOKEN, verify_ssl=False)
    app.state.client = client
       
    # Initialize service
    service = DeviceService(client)

    # Pre-fetch the device list BEFORE the WS listener starts, so any
    # deviceOnline event for an unknown device is correctly flagged as new.
    await service.load_known_devices()

    # Start WebSocket
    # We pass the service.handle_ws_message as the callback
    ws_task = asyncio.create_task(client.listen_socket(on_message=service.handle_ws_message))

    # Start Periodic Task
    qssd_task = asyncio.create_task(periodic_sim_balance_qssd_task(client))
    simcard_no_task = asyncio.create_task(periodic_simcard_no_task(client))
    getparams_task = asyncio.create_task(periodic_getparams_task(client))
    getimsi_task = asyncio.create_task(periodic_getimsi_task(client))
    getpass_task = asyncio.create_task(periodic_getpass_task(client))

    # Initial Device Check & Command Sending
    try:
        devices = await client.get_devices()

        t950_devices = [
            d for d in devices
            if d.get("model") == "T950" or d.get("attributes", {}).get("model") == "T950"
        ]

        print(f"\n✅ Found {len(t950_devices)} T950 devices\n")

        # Send ALLPARAMS request only to online devices
        # (Original code logic preserved)
        for dev in t950_devices:
            dev_id = dev["id"] 
            status = dev.get("status")

            if status == "online":
                try:
                    resp = await client.send_command(dev_id, "bacmd:ALLPARAMS")
                    print("✅ Sent ALLPARAMS CMD:", resp)
                    # print("-------------------")
                except Exception as e:
                    print(f"❌ Failed to send ALLPARAMS to {dev_id}: {e}")

        print("\n✅ WebSocket live. Waiting for events...\n")

    except Exception as e:
        print(f"❌ Startup error: {e}")

    # Start FTP Server
    ftp_process = ftp_server.start_server()

    yield

    # SHUTDOWN
    print("\n🛑 Shutting down background tasks...")
    
    ftp_server.stop_server(ftp_process)
    
    if ws_task:
        ws_task.cancel()
    if qssd_task:
        qssd_task.cancel()
    if simcard_no_task:
        simcard_no_task.cancel()
    if getparams_task:
        getparams_task.cancel()
    if getimsi_task:
        getimsi_task.cancel()
    if getpass_task:
        getpass_task.cancel()

    # Wait for completion of cancelled tasks to avoid "Task was destroyed" warnings
    await asyncio.gather(
        ws_task,
        qssd_task,
        simcard_no_task,
        getparams_task,
        getimsi_task,
        getpass_task,
        return_exceptions=True
    )

    if client:
        await client.close()
    
    print("👋 Graceful shutdown complete.")

from httpserver import start_server

if __name__ == "__main__":
    start_server(lifespan)
