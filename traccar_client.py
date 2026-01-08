# traccar_client.py
import aiohttp
import json
import asyncio

class TraccarClient:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True, session: aiohttp.ClientSession = None):
        if base_url.endswith('/'):
            base_url = base_url.rstrip('/')
        self._base_url = base_url
        self._token = token
        self._verify_ssl = verify_ssl
        self._session = session
        self._closed_session = False

    async def _get_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._closed_session = True
        return self._session

    async def close(self):
        if self._closed_session and self._session:
            await self._session.close()
            self._session = None

    async def _call(self, path: str, params: dict = None):
        sess = await self._get_session()
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

        async with sess.get(url, headers=headers, params=params, ssl=self._verify_ssl) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}: {text}")
            return json.loads(text)

    async def _post(self, path: str, data: dict):
        sess = await self._get_session()
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

        async with sess.post(url, headers=headers, json=data, ssl=self._verify_ssl) as resp:
            text = await resp.text()
            if resp.status not in (200, 201, 202):
                raise RuntimeError(f"POST {resp.status}: {text}")
            return json.loads(text)

    async def get_device(self, dev_id: int):
        return await self._call(f"devices/{dev_id}")

    async def get_devices(self, params: dict = None):
        return await self._call("devices?all=true", params=params)

    # -----------------------------------------------------------
    # Send custom command
    # -----------------------------------------------------------
    async def send_command(self, device_id: int, data: str, no_queue: bool = True):
        payload = {
            "deviceId": device_id,
            "type": "custom",
            "attributes": {"data": data, "noQueue": no_queue}
        }
        return await self._post("commands/send", payload)

    # -----------------------------------------------------------
    # Update only attributes (safe: retrieves full object first)
    # -----------------------------------------------------------
    async def update_device_attributes(self, device_id: int, new_attrs: dict):
        dev = await self.get_device(device_id)

        attrs = dev.get("attributes", {})
        attrs.update(new_attrs)

        payload = {
            "id": device_id,
            "name": dev["name"],
            "uniqueId": dev["uniqueId"],
            "status": dev.get("status"),
            "model": dev.get("model"),
            "groupId": dev.get("groupId"),
            "contact": dev.get("contact"),
            "category": dev.get("category"),
            "attributes": attrs
        }

        sess = await self._get_session()
        url = f"{self._base_url}/devices/{device_id}"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

        async with sess.put(url, headers=headers, json=payload, ssl=self._verify_ssl) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                raise RuntimeError(f"PUT {resp.status}: {text}")

        print(f"✅ Saved device {device_id} attributes:", new_attrs)
        return True

    # -----------------------------------------------------------
    # WebSocket listener with auto-reconnect
    # -----------------------------------------------------------
    async def listen_socket(self, on_message=None):
        backoff = 1   # start with 1 second delay

        while True:
            sess = await self._get_session()
            url = f"{self._base_url}/socket?token={self._token}"
            print(f"🔗 Connecting WebSocket: {url}")

            try:
                async with sess.ws_connect(url, ssl=self._verify_ssl) as ws:
                    print("✅ WebSocket connected.")
                    backoff = 1  # reset on success

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            if on_message:
                                on_message(msg.data)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print("❌ WS internal error:", ws.exception())
                            break

                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSING
                        ):
                            print("⚠️ WS closed by server.")
                            break

            except Exception as e:
                print(f"❌ WS connection failed: {e}")

            # reconnect logic
            print(f"♻️ Reconnecting WebSocket in {backoff} seconds...")
            await asyncio.sleep(backoff)

            # increase delay up to max 30 seconds
            backoff = min(backoff * 2, 30)
