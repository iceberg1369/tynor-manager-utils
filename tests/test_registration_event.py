import asyncio
import json
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import DeviceService, device_type_to_model

# Mock TraccarClient
class MockTraccarClient:
    def __init__(self):
        self.get_devices = AsyncMock(return_value=[
            {"id": 100, "name": "خودرو 1"},
            {"id": 102, "name": "خودرو 3"},
            {"id": 101, "name": "خودرو 2"},
            {"id": 99, "name": "Other Device"}
        ])
        
        self.get_device = AsyncMock(return_value={
            "id": 105,
            "name": "New Device",
            "uniqueId": "12345",
            "model": "OldModel",
            "attributes": {"assignee": 10},
            "groupId": 1,
            "phone": "0912...",
            "category": "car",
            "disabled": False
        })
        
        self.update_device = AsyncMock(return_value=True)
        self.update_device_attributes = AsyncMock(return_value=True)

async def test_logic():
    print("TEST: device_type_to_model mapping...")
    # the cmd 29 dm is the firmware's DEVICE_MODEL (version.h): T950 = 50
    assert device_type_to_model(50) == "TYNOR-T950"
    assert device_type_to_model(95) == "TYNOR-T950"
    assert device_type_to_model(90) == "TYNOR-T900"
    assert device_type_to_model(120) == "TYNOR-T120"
    assert device_type_to_model(999) == "unknown"
    print("✅ Mapping OK")
    
    client = MockTraccarClient()
    service = DeviceService(client)
    
    print("TEST: generate_device_name...")
    name = await service.generate_device_name(user_id=10)
    print(f"Generated Name: {name}")
    # Highest ID is 102 with name "خودرو 3". Next should be "خودرو 4".
    # Wait, my logic finds max ID with name starting with "خودرو".
    # 100 -> "خودرو 1"
    # 101 -> "خودرو 2"
    # 102 -> "خودرو 3"
    # Last ID is 102. Name is "خودرو 3". Split -> "خودرو", "3". Return "خودرو 4".
    assert name == "خودرو 4"
    print("✅ Name Generation OK")

    print("TEST: handle_registration_event...")
    cmd_result = {
        "cmd": 29,
        "param": {
            "imei": "123456789012345",
            "imsi": "987654321098765",
            "spn": "Provider",
            "fw": 131,
            "ts": 1769341620,
            "dm": 50 # T950
        }
    }
    
    await service.handle_registration_event(105, cmd_result)
    
    # Verify update called
    client.update_device.assert_called_once()
    call_args = client.update_device.call_args[0] #(id, data)
    u_id = call_args[0]
    u_data = call_args[1]
    
    assert u_id == 105
    assert u_data["name"] == "خودرو 4"
    assert u_data["model"] == "TYNOR-T950"
    assert u_data["attributes"]["firmware"] == 131
    assert u_data["attributes"]["imsi"] == "987654321098765"
    # traccar's PUT clears any field left out, so the rest goes back as it was
    assert u_data["phone"] == "0912..."
    assert u_data["groupId"] == 1

    print("✅ Registration Handler OK")

    print("TEST: a dm the manager doesn't know keeps the device's model...")
    client = MockTraccarClient()
    service = DeviceService(client)
    await service.handle_registration_event(105, {"cmd": 29, "param": dict(cmd_result["param"], dm=999)})
    client.update_device.assert_called_once()
    assert client.update_device.call_args[0][1]["model"] == "OldModel"
    print("✅ Unknown dm OK")

if __name__ == "__main__":
    asyncio.run(test_logic())
