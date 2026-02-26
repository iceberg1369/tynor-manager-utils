import sys
import os
import json

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import find_newer_firmware

def test_firmware_lookup():
    print("Testing firmware lookup...")
    
    # Test case 1: Device 90, Firmware < Max (Should return list)
    print("\nTest Case 1: Device 90, FW 60000 (Expect > 0 results)")
    res1 = find_newer_firmware(90, 1, 60000)
    print(f"Result count: {len(res1)}")
    if len(res1) > 0:
        print("✅ Passed")
    else:
        print("❌ Failed")

    # Test case 2: Device 90, Firmware > Max (Should return empty)
    print("\nTest Case 2: Device 90, FW 200000 (Expect 0 results)")
    res2 = find_newer_firmware(90, 1, 200000)
    print(f"Result count: {len(res2)}")
    if len(res2) == 0:
        print("✅ Passed")
    else:
        print("❌ Failed")

    # Test case 3: Device 230, Firmware < Max (Should return 1)
    print("\nTest Case 3: Device 230, FW 100000 (Expect 1 result)")
    res3 = find_newer_firmware(230, 1, 100000)
    print(f"Result count: {len(res3)}")
    if len(res3) == 1 and res3[0]['device'] == 230:
        print("✅ Passed")
    else:
        print("❌ Failed")
        
    # Check data integrity
    if len(res3) > 0:
        print(f"Data check: {res3[0]}")

if __name__ == "__main__":
    test_firmware_lookup()
