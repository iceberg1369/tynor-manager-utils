import re
import asyncio
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# -----------------------------------------------------------
# USSD Parsing Logic (from ussd_parser.py)
# -----------------------------------------------------------

def parse_ussd_message(raw_data: str) -> Optional[str]:
    """
    Parses the raw data string to extract and decode the USSD message.
    Handles both Hex-encoded UTF-16BE and plain text formats.
    Returns the decoded message string, or None if no USSD pattern is found.
    """
    if not raw_data:
        return None

    # Regex to find content string in: +CUSD: 0, "<content>", 15  OR  CUSD: ...
    # We capture anything inside quotes to also support plain text responses
    match = re.search(r'\+?CUSD: \d+, "([^"]+)"', raw_data)
    if not match:
        return None

    content_str = match.group(1)
    
    # Check if it looks like Hex and try to decode
    # Heuristic: if it contains non-hex chars or is odd length, it's likely plain text
    is_hex = True
    if len(content_str) % 2 != 0:
        is_hex = False
    else:
        # check chars
        if not all(c in "0123456789ABCDEFabcdef" for c in content_str):
            is_hex = False

    decoded_msg = content_str
    if is_hex:
        try:
            # UCS2 / UTF-16BE decoding
            decoded_msg = bytes.fromhex(content_str).decode('utf-16be')
        except Exception:
            # Fallback if decode fails
            pass
            
    return decoded_msg

def extract_ussd_credit(message: str) -> Optional[str]:
    """
    Extracts credit balance from USSD message.
    Looks for digits/commas before 'ریال' (Rial) or 'Rial'.
    """
    if not message:
        return None
    
    # Regex for digits/commas before "ریال" (Rial) or "Rial" (English)
    # This matches "150,918Rial" or "150918 Rial" or "150000ریال"
    match = re.search(r'([\d,]+)\s*(?:Rial|ریال)', message, re.IGNORECASE)
    if match:
        raw_num = match.group(1)
        # Remove commas
        clean_num = raw_num.replace(",", "")
        return clean_num
    return None


# -----------------------------------------------------------
# Route Handler
# -----------------------------------------------------------

@router.get("/qussd.php")
@router.post("/qussd.php")
async def handle_qussd(request: Request):
    """
    Handle incoming QSSD data
    """
    # Access client from app state
    client = getattr(request.app.state, "client", None)
    
    query_params = request.query_params
    try:
        body = await request.json()
    except:
        body = await request.body()
        if body:
            try:
                body = body.decode('utf-8')
            except:
                pass

    print(f"\n📩 Received /qussd.php request from {request.client.host}:{request.client.port}")
    print(f"   Method: {request.method}")
    print(f"   URL: {request.url}")
    print(f"   Headers: {dict(request.headers)}")
    
    # Parse form data if available
    imei = None
    raw_data = None
    
    # Try parsing body as form data manually or via request
    if body and isinstance(body, str):
        # simple parse for "imei=...&data=..."
        from urllib.parse import parse_qs
        parsed = parse_qs(body)
        imei = parsed.get("imei", [None])[0]
        raw_data = parsed.get("data", [None])[0]
        
    if imei and raw_data:
        print(f"   [PARSED] IMEI: {imei}")
        print(f"   [PARSED] Raw Data: {raw_data}")
        
        # Parse USSD message
        decoded_msg = parse_ussd_message(raw_data)
        
        if decoded_msg:
            print(f"   ✅ [USSD MSG]: {decoded_msg}")
            
            # Extract Credit Balance
            credit_amount = extract_ussd_credit(decoded_msg)
            if credit_amount:
                print(f"   💰 [CREDIT]: {credit_amount}")
                
                if imei and client:
                    try:
                        # 1. Map IMEI -> Device ID
                        devs = await client.get_devices(params={"uniqueId": imei})
                        if devs:
                            dev_obj = devs[0]
                            d_id = dev_obj["id"]
                            # 2. Update 'balance' attribute
                            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            await client.update_device_attributes(d_id, {"balance": credit_amount, "balance_ts": ts})
                            print(f"   ✅ [BALANCE SAVED] Device {d_id} : {credit_amount} at {ts}")
                        else:
                            print(f"   ⚠️ Device not found for IMEI: {imei}")
                    except Exception as e:
                        print(f"   ❌ Failed to sync balance to device: {e}")
            else:
                print("   ℹ️ No credit balance found in message.")
        else:
             print("   ⚠️ No USSD pattern found in data.")

    return {"status": "ok", "message": "Data received"}
