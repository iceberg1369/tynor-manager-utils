import asyncio
import os
import sys
from unittest.mock import AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import ensure_reply_filters, SERVER_SKIP_ATTRIBUTES

COMPUTED = [{"id": 6, "attribute": "eventKey"}, {"id": 8, "attribute": "resultKey"}]


def mock_client(device_attrs, linked=(), computed=COMPUTED):
    client = AsyncMock()
    client.get_computed_attributes = AsyncMock(
        side_effect=lambda device_id=None: [a for a in computed if a["id"] in linked] if device_id else computed)
    client.get_device = AsyncMock(return_value={"id": 300, "attributes": dict(device_attrs)})
    return client


async def test_reply_filters():
    print("TEST: new device gets resultKey linked and the server list plus resultKey...")
    client = mock_client({"assignee": 10})
    await ensure_reply_filters(client, 300)
    client.add_permission_generic.assert_awaited_once_with("permissions", "deviceId", 300, "attributeId", 8)
    client.update_device_attributes.assert_awaited_once_with(
        300, {"filter.skipAttributes": SERVER_SKIP_ATTRIBUTES + ",resultKey"})
    print("✅ New device OK")

    print("TEST: a device's own list is kept and extended...")
    client = mock_client({"filter.skipAttributes": "in3,result,eventKey"}, linked={6})
    await ensure_reply_filters(client, 300)
    client.add_permission_generic.assert_awaited_once_with("permissions", "deviceId", 300, "attributeId", 8)
    client.update_device_attributes.assert_awaited_once_with(
        300, {"filter.skipAttributes": "in3,result,eventKey,resultKey"})
    print("✅ Existing list OK")

    print("TEST: a device that already has it is left alone...")
    client = mock_client({"filter.skipAttributes": SERVER_SKIP_ATTRIBUTES + ",resultKey"}, linked={8})
    await ensure_reply_filters(client, 300)
    client.add_permission_generic.assert_not_awaited()
    client.update_device_attributes.assert_not_awaited()
    print("✅ Already set up OK")

    print("TEST: resultKey missing on traccar links nothing...")
    client = mock_client({}, computed=[{"id": 6, "attribute": "eventKey"}])
    await ensure_reply_filters(client, 300)
    client.add_permission_generic.assert_not_awaited()
    print("✅ Missing attribute OK")


if __name__ == "__main__":
    asyncio.run(test_reply_filters())
