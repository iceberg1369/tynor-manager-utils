import asyncio
import os
import sys
from unittest.mock import AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from traccar_client import TraccarClient
from services import DeviceService

DEVICE = {
    "id": 300, "name": "خودرو 1", "uniqueId": "868298066798316", "status": "online",
    "model": "T950", "groupId": 1, "contact": "someone", "category": "car",
    "phone": "09121234567", "disabled": False, "expirationTime": "2027-01-01T00:00:00.000+00:00",
    "calendarId": 3, "positionId": 99, "lastUpdate": "2026-10-27T09:00:00.000+00:00",
    "attributes": {"assignee": 10, "imsi": "432113965290248"},
}


class FakeResponse:
    status = 200

    async def text(self):
        return ""


class FakeSession:
    def __init__(self):
        self.puts = []

    def put(self, url, headers=None, json=None, ssl=None):
        self.puts.append(json)
        session = self

        class Ctx:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, *exc):
                return False
        return Ctx()


def kept_fields(sent):
    """Every field of the fetched device except attributes/model must go back unchanged."""
    for k, v in DEVICE.items():
        if k not in ("attributes", "model", "name"):
            assert sent.get(k) == v, f"{k} changed: {sent.get(k)!r} != {v!r}"


async def test_device_update():
    print("TEST: update_device_attributes sends the whole device back...")
    session = FakeSession()
    client = TraccarClient("http://traccar/api", "token", session=session)
    client.get_device = AsyncMock(side_effect=lambda _id: {**DEVICE, "attributes": dict(DEVICE["attributes"])})
    await client.update_device_attributes(300, {"balance": "100"})
    sent = session.puts[-1]
    kept_fields(sent)
    assert sent["model"] == "T950" and sent["name"] == "خودرو 1"
    assert sent["attributes"] == {"assignee": 10, "imsi": "432113965290248", "balance": "100"}
    await client.update_device_attributes(300, {"sn": "95260811115"}, model="TYNOR-T950")
    assert session.puts[-1]["model"] == "TYNOR-T950"
    kept_fields(session.puts[-1])
    print("✅ update_device_attributes OK")

    print("TEST: update_imsi keeps phone and the other fields...")
    client = AsyncMock()
    client.get_device = AsyncMock(return_value={**DEVICE, "attributes": dict(DEVICE["attributes"], **{"SIMCARD No": "0912"})})
    service = DeviceService(client)
    import tasks
    tasks.simcard_no_check_for_device = AsyncMock()
    tasks.sim_balance_qssd_for_device = AsyncMock()
    await service.update_imsi(300, "432350000000000")
    sent = client.update_device.call_args[0][1]
    kept_fields(sent)
    assert sent["attributes"]["imsi"] == "432350000000000" and "SIMCARD No" not in sent["attributes"]
    print("✅ update_imsi OK")

    print("TEST: handle_registration_event keeps phone and the other fields...")
    client = AsyncMock()
    client.get_device = AsyncMock(return_value={**DEVICE, "attributes": dict(DEVICE["attributes"])})
    client.get_devices = AsyncMock(return_value=[])
    service = DeviceService(client)
    await service.handle_registration_event(300, {"param": {"imsi": "432113965290248", "dm": 50, "fw": 131330}})
    sent = client.update_device.call_args[0][1]
    kept_fields(sent)
    assert sent["model"] == "TYNOR-T950" and sent["attributes"]["firmware"] == 131330
    print("✅ handle_registration_event OK")


if __name__ == "__main__":
    asyncio.run(test_device_update())
