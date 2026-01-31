# Traccar Middleware Service

This project is a Python-based middleware service designed to extend the capabilities of the Traccar GPS tracking platform. It provides custom API endpoints, handles OTP authentication, processes USSD commands, and manages automated device events via WebSocket integration.

## Features

- **Custom Authentication**: Implements OTP (One-Time Password) flow using SMS (Ghasedak) for user verification and session token generation.
- **Event Handling**: Listens to Traccar WebSocket events to react to device commands and status changes (e.g., Device Registration/Initialization Cmd 29).
- **Device Management**: Automates device naming ("خودرو X") and attribute updates based on incoming data.
- **USSD Parsing**: Parses USSD responses to extract useful data like SIM balance.
- **Periodic Tasks**: scheduling of custom commands to devices.

## Requirements

This project requires Python 3.8+ and the following packages:

- `fastapi`
- `uvicorn`
- `aiohttp`
- `requests`
- `pydantic`
- `ghasedak-sms` (Ensure you have the correct library for SMS)

## Installation

1.  Clone the repository or download the source code.
2.  Install the required dependencies using pip:

    ```bash
    pip install -r requirements.txt
    ```

    *(Note: If `ghasedak-sms` is not the exact package name you are using, please adjust accordingly based on your specific library).*

3.  Configure the application:
    - Edit `config.py` to set your Traccar URL, Admin Token, SMS API Key, and other secrets.

## Running the Project

To start the service, run the `main.py` script:

```bash
python main.py
```

The server will start on `http://0.0.0.0:8088`.

## structure

- `main.py`: Entry point, initializes FastAPI app, Traccar Client, and background tasks.
- `api/`: Contains API route handlers (`auth.py`, `device.py`, etc.).
- `services.py`: Business logic for event handling and device management.
- `traccar_client.py`: Async client for interacting with the Traccar API.
- `tasks.py`: Periodic background tasks.

## API Endpoints

### Authentication
- **POST** `/api/otprequest`
    - **Body**: `{"client_secret": "...", "phone": "..."}`
    - **Description**: Requests an OTP via SMS for the given phone number.
- **POST** `/api/otpverify`
    - **Body**: `{"client_secret": "...", "phone": "...", "sms_message": "1234"}`
    - **Description**: Verifies the OTP and returns the registered user session token.

### Device Management
- **POST** `/api/device`
    - **Body**: `{"user": "...", "imei": "...", "dp": "...", "client_secret": "..."}`
    - **Description**: Registers or initializes a device for a user.
- **POST** `/api/checkDeviceInfo`
    - **Body**: `{"user": "...", "imei": "...", "client_secret": "..."}`
    - **Description**: Checks if a device can be registered.

### Legacy Support (PHP Compat)
- **GET/POST** `/qussd.php`
    - **Params**: `imei`, `data`
    - **Description**: Receives USSD response data from devices, parses credit balance, and updates the device attribute.
- **GET/POST** `/fota.php`
    - **Params**: `imei`, `sr`, `d` (device type), `fw` (current firmware), `rev`
    - **Description**: Checks for available firmware updates and returns FTP download links.
