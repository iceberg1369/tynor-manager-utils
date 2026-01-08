# main.py
import asyncio
import re
import uvicorn
import subprocess
import sys
import os
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Request

import config
from traccar_client import TraccarClient
from services import DeviceService
from tasks import periodic_qssd_task
from tasks import periodic_getparams_task
from database import init_db
from api.fota import router as fota_router
from api.ussd import router as ussd_router
from api.auth import router as auth_router

# Global reference to client for the route handler to use
# Ideally we would use dependency injection in FastAPI but a global is fine for this simple port to match original logic
client: Optional[TraccarClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    global client
    
    # Initialize Database
    init_db()

    client = TraccarClient(config.BASE_URL, config.TOKEN, verify_ssl=False)
    app.state.client = client
    
    # Initialize service
    service = DeviceService(client)

    # Start WebSocket
    # We pass the service.handle_ws_message as the callback
    ws_task = asyncio.create_task(client.listen_socket(on_message=service.handle_ws_message))

    # Start Periodic Task
    #qssd_task = asyncio.create_task(periodic_qssd_task(client))
    getparams_task = asyncio.create_task(periodic_getparams_task(client))

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

            if status == "online" and dev["id"] == 115:
                try:
                    # resp = await client.send_command(dev_id, "bacmd:ALLPARAMS")
                    # print("✅ Sent ALLPARAMS CMD:", resp)
                    print("-------------------")
                except Exception as e:
                    print(f"❌ Failed to send ALLPARAMS to {dev_id}: {e}")

        print("\n✅ WebSocket live. Waiting for events...\n")

    except Exception as e:
        print(f"❌ Startup error: {e}")

    # Start FTP Server
    ftp_process = None
    try:
        ftp_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ftp_server.py')
        ftp_process = subprocess.Popen([sys.executable, ftp_script])
        print(f"🚀 FTP Server started with PID {ftp_process.pid}")
    except Exception as e:
        print(f"❌ Failed to start FTP Server: {e}")

    yield

    # SHUTDOWN
    print("\n🛑 Shutting down background tasks...")
    
    if ftp_process:
        print("🛑 Stopping FTP Server...")
        ftp_process.terminate()
        try:
            ftp_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ftp_process.kill()
    
    if ws_task:
        ws_task.cancel()
    # if qssd_task:
    #     qssd_task.cancel()
    if getparams_task:
        getparams_task.cancel()

    # Wait for completion
    #await asyncio.gather(ws_task, qssd_task, getparams_task, return_exceptions=True)

    if client:
        await client.close()
    
    print("👋 Graceful shutdown complete.")

app = FastAPI(lifespan=lifespan)
app.include_router(fota_router)
app.include_router(ussd_router)
app.include_router(auth_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8088)
