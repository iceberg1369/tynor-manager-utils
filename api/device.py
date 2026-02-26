
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

    try:
        body = await request.json()
    except:
        return {"success": False, "message": "Invalid JSON body"}
    
    # Extract fields with defaults
    user = body.get('user')
    imei = body.get('imei')
    frmUser = body.get('from')
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

    user_id = await client.find_user_id_by_username(user)
            
    # 7. Assignment Logic
    attributes = device.get('attributes', {})
    assignee = attributes.get('assignee')

    if assignee is None or frmUser is not None:
        if user_id > 0:
            # Assign user to device
            try:
                await client.add_permission(user_id, device['id'])
            except Exception as e:
                print(f"Failed to add permission: {e}")
                # Fallthrough? PHP logic proceeds to update attribute even if assign fails? 
                # It calls assignUserDevice then updateAttributes.

            if frmUser is not None:
                # unlink device from old user
                try:
                    frm_user_id = await client.find_user_id_by_username(frmUser)
                    print(f"from_user_id:{frm_user_id} deviceid:{device['id']}")
                    
                    if frm_user_id > 0:
                        remove_permission_resp = await client.remove_permission(frm_user_id, device['id'])
                        print(f"remove_permission output: {remove_permission_resp}")
                except Exception as e:
                    print(f"Failed to remove permission: {e}")
            
            
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

    # 8. Send Command to the device
    cmd_data = {
        "c": 29,
        "param": {
            "owner": user,
            "devicePassword": device_password
        }
    }
    # Original PHP sends it as a JSON STRING inside the data attribute
    cmd_data_str = json.dumps(cmd_data)
    
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


@router.post("/api/check")
async def handle_check_device_info(request: Request):
    try:
        body = await request.json()
    except:
        return {"success": False, "message": "Invalid JSON body"}

    print("[CHECK] Incoming request")
    print(f"[CHECK] Method: {request.method}")
    print(f"[CHECK] URL: {request.url}")
    print(f"[CHECK] Query: {dict(request.query_params)}")
    print(f"[CHECK] Headers: {dict(request.headers)}")
    print(f"[CHECK] Body: {body}")
    
    user = body.get('user')
    imei = body.get('imei')
    frmUser = body.get('from')
    client_secret = body.get('client_secret')

    if not user and not imei and not client_secret:
         pass # matching PHP quirk?
    
    if not user or not imei or not client_secret:
         print('The client_secret, phone, and imei parameters are required')
         return {
            'success': False,
            'message': 'The client_secret, phone, and imei parameters are required'
        }

    if client_secret != config.CLIENT_SECRET:
         print('The client_secret parameter does not match.')
         return {
            'success': False,
            'message': 'The client_secret parameter does not match.'
        }


    client: TraccarClient = getattr(request.app.state, "client", None)
    if not client:
        print("Internal Server Error")
        return {"success": False, "message": "Internal Server Error"}

    devices = await client.get_devices(params={"uniqueId": imei})
    if not devices:
        print(f"device {imei} not found!!!!")
        return {
            'success': False,
            'message': f"device {imei} not found!!!!"
        }
    
    device = devices[0]
    
    if device.get('status') != 'online':
        print("device not online")
        return {
            'success': False,
            'message': "device not online"
        }

    attributes = device.get('attributes', {})
    assignee = attributes.get('assignee')

    if assignee is None or frmUser is not None:
        # Check user existence
        user_id = await client.find_user_id_by_username(user)
        
        if user_id > 0:
            pass # User found, assignments possible
        else:
             print("user not found")
             return {
                'success': False,
                'message': "user not found"
            }
    else:
        print("device already registered")
        return {
            'success': False,
            'message': "device already registered"
        }

    print("device can be registered")
    return {
        'success': True,
        'message': "device can be registered"
    }
