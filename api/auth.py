import logging
import random
import time
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import ghasedak_sms
import config
from traccar_client import TraccarClient

router = APIRouter()
logger = logging.getLogger("auth")

# In-memory OTP store
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

async def create_user_and_get_token(phone: str):
    """
    Creates user if not exists, assigns notifications, and returns a long-lived session token.
    Mirrors the provided PHP implementation.
    """
    admin_client = TraccarClient(config.BASE_URL, config.TOKEN)
    token = None
    
    try:
        # 1. Login/Check Admin (Client uses token, so practically logged in)
        
        # 2. Check if user exists
        users = await admin_client.get_users({"search": phone})
        user = next((u for u in users if u.get("email") == phone or u.get("name") == phone), None)
        
        password = "123456"
        is_new_user = False
        
        if not user:
            # Create User
            reg_date = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            attributes = {
                "registrationDate": reg_date,
                "timezone": "Asia/Tehran",
                "Distance Unit": "km",
                "Volume Unit": "ltr",
                "Speed Unit": "kmh"
            }
            
            user_payload = {
                "name": phone,
                "email": phone, # Using phone as email
                "phone": phone, # Added phone field
                "password": password,
                "attributes": attributes
            }
            
            try:
                user = await admin_client.add_user(user_payload)
                is_new_user = True
                logger.info(f"Created new user: {phone}")
            except Exception as e:
                logger.error(f"Failed to create user {phone}: {e}")
                raise e
        else:
            # Update User logic from PHP: if token matches logic? 
            # PHP: if(empty($user->token)) update... 
            # We don't have easy access to 'token' field unless we fetched full object.
            # get_users returns list of objects, usually doesn't include 'token' (API token) unless full.
            # But we are generating SESSION token later anyway.
            # We will skip update unless necessary.
            pass

        # 3. Add Notifications (If new user)
        if is_new_user:
            # List of notifications to add
            # PHP creates them (as Admin) and implicitly or explicitly we should link them to User.
            # We will Create and then Permission Link.
            
            # Helper to build dict structure matching PHP: id=-1, always=True
            def make_notif(ntype, notificators, attributes):
                return {
                    "id": -1,
                    "type": ntype,
                    "always": True,
                    "notificators": notificators,
                    "attributes": attributes
                }

            notif_defs = [
                make_notif("ignitionOn", "web", {}),
                make_notif("ignitionOff", "web", {}),
                make_notif("deviceUnknown", "web", {}),
                make_notif("commandResult", "web", {}),
                make_notif("deviceOnline", "web", {}),
                make_notif("deviceOffline", "web", {}),
                make_notif("deviceStopped", "web", {}),
                make_notif("deviceMoving", "web", {}),
                
                make_notif("ignitionOn", "firebase", {}),
                make_notif("ignitionOff", "firebase", {}),
                
                make_notif("alarm", "web", {"alarms": "idle"}),
                make_notif("alarm", "web", {"alarms": "overspeed"}),
                make_notif("alarm", "web", {"alarms": "powerCut"}),
                make_notif("alarm", "web", {"alarms": "vibration"}),
                make_notif("alarm", "web", {"alarms": "lowPower"}),
                make_notif("alarm", "web", {"alarms": "tow"}),
                
                make_notif("alarm", "firebase", {"alarms": "idle"}),
                make_notif("alarm", "firebase", {"alarms": "overspeed"}),
                make_notif("alarm", "firebase", {"alarms": "powerCut"}),
                make_notif("alarm", "firebase", {"alarms": "vibration"}),
                make_notif("alarm", "firebase", {"alarms": "lowPower"}),
                make_notif("alarm", "firebase", {"alarms": "tow"}),
            ]
            
            for nd in notif_defs:
                try:
                    # Create notification
                    notif = await admin_client.create_notification(nd)
                    # Link to user
                    if 'id' in notif:
                        await admin_client.add_permission_generic("permissions", "userId", user['id'], "notificationId", notif['id'])
                except Exception as e:
                    logger.warning(f"Failed to add notification {nd['type']}: {e}")

    finally:
        await admin_client.close()
        
    # 4. Login as User and Request Token
    # Use valid expiration from PHP: 2062-10-23T20:30:00.000Z
    user_client = TraccarClient(config.BASE_URL, token=None)
    try:
        await user_client.login(phone, password)
        raw_token = await user_client.request_token("2062-10-23T20:30:00.000Z")
        
        # Determine format
        if isinstance(raw_token, dict) and 'token' in raw_token:
            token = raw_token['token']
        elif isinstance(raw_token, dict) and 'data' in raw_token:
             token = raw_token['data']
        else:
             token = str(raw_token)
             
    except Exception as e:
        logger.error(f"Failed to generate token for {phone}: {e}")
        # Fallback? Or raise
        raise HTTPException(status_code=500, detail=f"Token generation failed: {e}")
    finally:
        await user_client.close()

    return token

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
    
    # Use real token generation
    try:
        token = await create_user_and_get_token(data.phone)
    except Exception as e:
        logger.error(f"Token generation error: {e}")
        return {"success": False, "message": f"Login failed: {e}"}
    
    return {
        "success": True,
        "phone": data.phone,
        "token": token
    }
