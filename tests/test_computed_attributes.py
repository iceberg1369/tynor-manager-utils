import asyncio
import os
import sys
from unittest.mock import AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import ensure_computed_attributes, TYNOR_COMPUTED_ATTRIBUTES

ALL = [dict(a, id=4 + i) for i, a in enumerate(TYNOR_COMPUTED_ATTRIBUTES)]


def mock_client(existing):
    client = AsyncMock()
    client.get_computed_attributes = AsyncMock(return_value=existing)
    client.create_computed_attribute = AsyncMock(side_effect=lambda a: dict(a, id=100))
    return client


async def test_computed_attributes():
    print("TEST: an empty server gets all of them...")
    client = mock_client([{"id": 1, "attribute": "batteryLevel", "expression": "io113 ? io113: null"}])
    created = await ensure_computed_attributes(client)
    assert client.create_computed_attribute.await_count == len(TYNOR_COMPUTED_ATTRIBUTES)
    assert [a["attribute"] for a in created] == [a["attribute"] for a in TYNOR_COMPUTED_ATTRIBUTES]
    print("✅ Empty server OK")

    print("TEST: only the missing one is created...")
    client = mock_client([a for a in ALL if a["attribute"] != "resultKey"])
    await ensure_computed_attributes(client)
    client.create_computed_attribute.assert_awaited_once()
    assert client.create_computed_attribute.await_args.args[0]["attribute"] == "resultKey"
    assert "id" not in client.create_computed_attribute.await_args.args[0]
    print("✅ Missing one OK")

    print("TEST: a server that has them all is left alone...")
    client = mock_client(ALL)
    assert await ensure_computed_attributes(client) == []
    client.create_computed_attribute.assert_not_awaited()
    print("✅ All present OK")

    print("TEST: a different expression under the same name is not touched...")
    client = mock_client([dict(a, expression="ignition") if a["attribute"] == "ignition" else a for a in ALL])
    assert await ensure_computed_attributes(client) == []
    client.create_computed_attribute.assert_not_awaited()
    print("✅ Different expression OK")


if __name__ == "__main__":
    asyncio.run(test_computed_attributes())
