import asyncio
import os
import sys
from unittest.mock import AsyncMock, call

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import services
from services import DeviceService, SERVER_SKIP_ATTRIBUTES

# ids as on the production server
COMPUTED = [{"id": 4, "attribute": "alarm"}, {"id": 5, "attribute": "valid"}, {"id": 6, "attribute": "eventKey"},
            {"id": 7, "attribute": "ignition"}, {"id": 8, "attribute": "resultKey"}, {"id": 9, "attribute": "stopKey"}]


def mock_client():
    client = AsyncMock()
    client.get_computed_attributes = AsyncMock(side_effect=lambda device_id=None: [] if device_id else COMPUTED)
    client.get_device = AsyncMock(return_value={"id": 300, "uniqueId": "867857033905725", "attributes": {}})
    return client


async def test_new_device():
    started = []
    services.DeviceService._provision_new_device = lambda self, device_id, delay=120: started.append(device_id) or asyncio.sleep(0)

    print("TEST: a device traccar just created gets the three filter keys, not alarm/valid/ignition...")
    client = mock_client()
    service = DeviceService(client)
    await service._handle_device_online(300)
    await asyncio.sleep(0)
    assert client.add_permission_generic.await_args_list == [
        call("permissions", "deviceId", 300, "attributeId", 6),
        call("permissions", "deviceId", 300, "attributeId", 8),
        call("permissions", "deviceId", 300, "attributeId", 9)]
    client.update_device_attributes.assert_awaited_once_with(
        300, {"filter.skipAttributes": SERVER_SKIP_ATTRIBUTES + ",eventKey,resultKey,stopKey"})
    assert started == [300]
    print("✅ New device OK")

    print("TEST: a device known at startup is left alone...")
    client = mock_client()
    service = DeviceService(client)
    service.known_device_ids = {300}
    await service._handle_device_online(300)
    client.add_permission_generic.assert_not_awaited()
    client.update_device_attributes.assert_not_awaited()
    print("✅ Known device OK")

    print("TEST: a traccar error doesn't stop provisioning...")
    client = mock_client()
    client.get_computed_attributes = AsyncMock(side_effect=RuntimeError("traccar down"))
    started.clear()
    await DeviceService(client)._handle_device_online(300)
    await asyncio.sleep(0)
    assert started == [300]
    print("✅ Error OK")


if __name__ == "__main__":
    asyncio.run(test_new_device())
