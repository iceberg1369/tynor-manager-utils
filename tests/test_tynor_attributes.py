import asyncio
import os
import sys
from unittest.mock import AsyncMock, call

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import ensure_tynor_attributes, SERVER_SKIP_ATTRIBUTES

# ids as on the production server
COMPUTED = [{"id": 1, "attribute": "batteryLevel"}, {"id": 4, "attribute": "alarm"}, {"id": 5, "attribute": "valid"},
            {"id": 6, "attribute": "eventKey"}, {"id": 7, "attribute": "ignition"}, {"id": 8, "attribute": "resultKey"},
            {"id": 9, "attribute": "stopKey"}]


def mock_client(device_attrs, linked=(), computed=COMPUTED):
    client = AsyncMock()
    client.get_computed_attributes = AsyncMock(
        side_effect=lambda device_id=None: [a for a in computed if a["id"] in linked] if device_id else computed)
    client.get_device = AsyncMock(return_value={"id": 300, "attributes": dict(device_attrs)})
    return client


def links(*ids):
    return [call("permissions", "deviceId", 300, "attributeId", i) for i in ids]


async def test_tynor_attributes():
    print("TEST: new device gets all six linked and the server list plus eventKey,resultKey,stopKey...")
    client = mock_client({"assignee": 10})
    await ensure_tynor_attributes(client, 300)
    assert client.add_permission_generic.await_args_list == links(4, 5, 6, 7, 8, 9)
    client.update_device_attributes.assert_awaited_once_with(
        300, {"filter.skipAttributes": SERVER_SKIP_ATTRIBUTES + ",eventKey,resultKey,stopKey"})
    print("✅ New device OK")

    print("TEST: only the missing links and skip keys are added, the device's own list is kept...")
    client = mock_client({"filter.skipAttributes": "in3,result,resultKey"}, linked={1, 8})
    await ensure_tynor_attributes(client, 300)
    assert client.add_permission_generic.await_args_list == links(4, 5, 6, 7, 9)
    client.update_device_attributes.assert_awaited_once_with(
        300, {"filter.skipAttributes": "in3,result,resultKey,eventKey,stopKey"})
    print("✅ Partly set up OK")

    print("TEST: a device that has everything (like 259) is left alone...")
    client = mock_client({"filter.skipAttributes": SERVER_SKIP_ATTRIBUTES + ",eventKey,resultKey,stopKey"},
                         linked={4, 5, 6, 7, 8, 9})
    await ensure_tynor_attributes(client, 300)
    client.add_permission_generic.assert_not_awaited()
    client.update_device_attributes.assert_not_awaited()
    print("✅ Already set up OK")

    print("TEST: an attribute missing on traccar is skipped, the rest are linked...")
    client = mock_client({}, computed=[a for a in COMPUTED if a["attribute"] != "alarm"])
    await ensure_tynor_attributes(client, 300)
    assert client.add_permission_generic.await_args_list == links(5, 6, 7, 8, 9)
    print("✅ Missing attribute OK")


if __name__ == "__main__":
    asyncio.run(test_tynor_attributes())
