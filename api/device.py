
import json
from fastapi import APIRouter, Request
from pydantic import BaseModel
import config
from utils import is_imei
from traccar_client import TraccarClient

router = APIRouter()

class DeviceRequest(BaseModel):
    user: str = None
    imei: str = None
    dp: str = None      # devicePassword
    client_secret: str = None

@router.post("/api/device")
async def handle_device_request(request: Request):
    # Try parsing JSON body manually to handle potential issues or use Pydantic if cleaner
    # Using manual parse to match PHP style of reading body
    try:
        body = await request.json()
    except:
        return {"success": False, "message": "Invalid JSON body"}
    
    # Extract fields with defaults
    user = body.get('user')
    imei = body.get('imei')
    device_password = body.get('dp')
    client_secret = body.get('client_secret')

    # 1. Validate existence
    if not user and not imei and not client_secret:
        # The PHP code checks if ALL are empty. 
        # So if any is missing -> error.
        pass

    if not user or not imei or not client_secret:
         return {
            'success': False,
            'message': 'The client_secret, phone, and imei parameters are required'
        }

    # 2. Validate Secret
    # matchSecretKey in PHP likely checks hardcoded or config
    if client_secret != config.CLIENT_SECRET: # Assuming config has the matching secret
         return {
            'success': False,
            'message': 'The client_secret parameter does not match.'
        }

    # 3. Validate IMEI
    if not is_imei(imei):
        return {
            'success': False,
            'message': f"invalid IMEI:{imei}"
        }

    client: TraccarClient = getattr(request.app.state, "client", None)
    if not client:
        return {"success": False, "message": "Internal Server Error: Traccar Client unavailable"}

    # 4. Get Device
    devices = await client.get_devices(params={"uniqueId": imei})
    if not devices:
        return {
            'success': False,
            'message': f"device {imei} not found!!!!"
        }
    
    device = devices[0]
    
    # 5. Check Online
    if device.get('status') != 'online':
        return {
            'success': False,
            'message': "device not online"
        }

    # 6. Find User ID

    users = await client.get_users() # fetch all for now or use search if list is huge?


    user_id = 0
    target_user_obj = None
    for u in users:
        if u.get('email') == user or u.get('name') == user or u.get('login') == user:
            user_id = u.get('id')
            target_user_obj = u
            break
            
    # 7. Assignment Logic
    attributes = device.get('attributes', {})
    assignee = attributes.get('assignee')

    if assignee is None:
        if user_id > 0:
            # Assign user to device
            try:
                await client.add_permission(user_id, device['id'])
            except Exception as e:
                print(f"Failed to add permission: {e}")
                # Fallthrough? PHP logic proceeds to update attribute even if assign fails? 
                # It calls assignUserDevice then updateAttributes.
            
            # Update assignee attribute
            new_attrs = {"assignee": user_id}
            await client.update_device_attributes(device['id'], new_attrs)
        else:
            return {
                'success': False,
                'message': "user not found"
            }
    elif int(assignee) != int(user_id):
        return {
            'success': False,
            'message': "device already registered"
        }

    # 8. Send Command
    # PHP: $registerCommand = "{\\\"c\\\":29, \\\"param\\\":{\\\"owner\\\":\\\"${user}\\\",\\\"devicePassword\\\":\\\"${devicePassword}\\\"}}";
    # Note proper JSON escaping in Python string for the inner JSON
    
    # Structure for "data" attribute in custom command
    cmd_data = {
        "c": 29,
        "param": {
            "owner": user,
            "devicePassword": device_password
        }
    }
    # Original PHP sends it as a JSON STRING inside the data attribute
    cmd_data_str = json.dumps(cmd_data)
    
    # The PHP code wraps it further?
    # $attrs = '{"data":  "' . $registerCommand . '"}';
    # gps::commandSend(..., "custom", $attrs);
    
    # Our client.send_command does:
    # payload = { type: custom, attributes: { data: data } }
    # So we just pass the inner string to send_command
    
    try:
        resp = await client.send_command(device['id'], cmd_data_str)
        # Verify success? TraccarClient implementation returns JSON. 
        # If it didn't raise exception, it's likely 200/202.
        
        return {
            'success': True,
            'message': "device command sent"
        }
    except Exception as e:
        print(f"Command send failed: {e}")
        return {
            'success': False,
            'message': "device command send failed!"
        }


@router.post("/api/checkDeviceInfo")
async def handle_check_device_info(request: Request):
    try:
        body = await request.json()
    except:
        return {"success": False, "message": "Invalid JSON body"}
    
    user = body.get('user')
    imei = body.get('imei')
    client_secret = body.get('client_secret')

    if not user and not imei and not client_secret:
         pass # matching PHP quirk?
    
    if not user or not imei or not client_secret:
         return {
            'success': False,
            'message': 'The client_secret, phone, and imei parameters are required'
        }

    if client_secret != config.CLIENT_SECRET:
         return {
            'success': False,
            'message': 'The client_secret parameter does not match.'
        }


    client: TraccarClient = getattr(request.app.state, "client", None)
    if not client:
        return {"success": False, "message": "Internal Server Error"}

    devices = await client.get_devices(params={"uniqueId": imei})
    if not devices:
        return {
            'success': False,
            'message': f"device {imei} not found!!!!"
        }
    
    device = devices[0]
    
    if device.get('status') != 'online':
        return {
            'success': False,
            'message': "device not online"
        }

    attributes = device.get('attributes', {})
    assignee = attributes.get('assignee')

    if assignee is None:
        # Check user existence
        users = await client.get_users()
        user_id = 0
        for u in users:
             if u.get('email') == user or u.get('name') == user or u.get('login') == user:
                user_id = u.get('id')
                break
        
        if user_id > 0:
            pass # User found, assignments possible
        else:
             return {
                'success': False,
                'message': "user not found"
            }
    else:
        return {
            'success': False,
            'message': "device already registered"
        }

    return {
        'success': True,
        'message': "device can be registered"
    }
