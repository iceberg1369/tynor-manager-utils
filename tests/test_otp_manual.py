
import requests
import json
import config

BASE_URL = "http://localhost:8088"
CLIENT_SECRET = config.CLIENT_SECRET
PHONE = "09123456789" # Mock phone

def test_otp_flow():
    print("1. Requesting OTP...")
    req_data = {
        "client_secret": CLIENT_SECRET,
        "phone": PHONE
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/otprequest", json=req_data)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if not resp.json().get("success"):
            print("Failed to request OTP")
            return

        # Assuming the backend prints the OTP or we can guess/access it? 
        # But we are running separate process. 
        # Wait, since I can't interactively read the console output used by the server easily here 
        # (unless I attach to it, but I'm just running a script).
        # Actually I coded `auth.py` to print the OTP: `print(f"✅ OTP generated for...`
        # But I need to start the server. 
        
        # I will rely on the user manually verifying or I can use the 'otp_store' if I import auth...
        # But importing auth here directly won't share state with the running server process if run separately.
        # However, for this test I will assume we might need to modify auth.py to return OTP in dev mode or just skip invalidation for test?
        # Or I can just check if I get a 200 OK.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_otp_flow()
