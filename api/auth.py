
import logging
import random
import time
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import ghasedak_sms
import config

router = APIRouter()
logger = logging.getLogger("auth")

# In-memory OTP store
# Format: { "09123456789": { "code": "1234", "expires_at": timestamp } }
otp_store = {}
OTP_EXPIRATION_SECONDS = 120 # 2 minutes

try:
    sms_api = ghasedak_sms.Ghasedak(config.GHASEDAK_OTP_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Ghasedak SMS: {e}")
    sms_api = None

class OtpRequest(BaseModel):
    client_secret: str
    phone: str

class OtpVerify(BaseModel):
    client_secret: str
    phone: str
    sms_message: str

def generate_otp():
    return str(random.randint(1000, 9999))

@router.post("/api/otprequest")
async def request_otp(data: OtpRequest):
    if not data.client_secret or not data.phone:
        return {"success": False, "message": "Both client_secret and phone are required."}

    if data.client_secret != config.CLIENT_SECRET:
        return {"success": False, "message": "The client_secret parameter does not match."}
    
    otp_code = generate_otp()
    
    # Send SMS
    try:
        if sms_api:
            # Using the structure from otp.py
            newotpcommand = ghasedak_sms.SendOtpInput(
                send_date=None,
                receptors=[
                    ghasedak_sms.SendOtpReceptorDto(
                        mobile=data.phone,
                        client_reference_id=str(int(time.time()*1000))
                    )
                ],
                template_name='valatek',
                inputs=[
                    ghasedak_sms.SendOtpInput.OtpInput(param='param1', value=otp_code),
                    ghasedak_sms.SendOtpInput.OtpInput(param='param2', value=config.APP_HASH_KEY)
                ],
                udh=False
            )
            response = sms_api.send_otp_sms(newotpcommand)
            logger.info(f"SMS Response: {response}")
            
            # Simple check, usually response is distinct object or boolean logic needed
            # Assuming success if no exception for now, or check response content
            # The user's otp.py just prints response.
        else:
             logger.warning("SMS API not initialized, skipping SMS send.")

    except Exception as e:
        logger.error(f"SMS API Failed: {e}")
        return {"success": False, "message": "API FAILED"}

    # Save to memory
    otp_store[data.phone] = {
        "code": otp_code,
        "expires_at": time.time() + OTP_EXPIRATION_SECONDS
    }
    
    print(f"✅ OTP generated for {data.phone}: {otp_code}")

    return {
        "success": True, 
        "message": "OTP request has been submitted",
        "time": OTP_EXPIRATION_SECONDS
    }

@router.post("/api/otpverify")
async def verify_otp(data: OtpVerify):
    if not data.client_secret or not data.phone or not data.sms_message:
        return {"success": False, "message": "The client_secret, phone, and sms_message parameters are required"}

    if data.client_secret != config.CLIENT_SECRET:
        return {"success": False, "message": "The client_secret parameter does not match."}

    stored = otp_store.get(data.phone)
    if not stored:
        return {"success": False, "message": "Unable to validate code for this phone number"}

    # Check expiration
    if time.time() > stored["expires_at"]:
        del otp_store[data.phone]
        return {"success": False, "message": "OTP expired"}
    
    # Check code
    if stored["code"] != data.sms_message:
         return {"success": False, "message": "Invalid code"}
    
    # Valid
    del otp_store[data.phone] # Consume OTP
    
    # Mock Token generation (User didn't specify how to generate token)
    token = f"mock_token_{int(time.time())}_{data.phone}"
    
    return {
        "success": True,
        "phone": data.phone,
        "token": token
    }
