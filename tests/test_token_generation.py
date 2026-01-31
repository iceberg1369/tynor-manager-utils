import sys
import os
import asyncio
import logging

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock config if needed, or import real one
import config

# We need to ensure we can import traccar_client from root
try:
    from api.auth import create_user_and_get_token
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Sys Path: {sys.path}")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_token_gen():
    phone = "09123456789"
    print(f"Testing token generation for {phone}...")
    
    try:
        token = await create_user_and_get_token(phone)
        if token:
            print(f"✅ Success! Token received: {token}")
            print(f"Token length: {len(str(token))}")
        else:
            print("❌ Failed: Token is None")
    except Exception as e:
        print(f"X Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if not config.TOKEN:
        print("WARNING: Config TOKEN is empty, test will likely fail.")
        
    asyncio.run(test_token_gen())
