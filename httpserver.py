
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import config
from api.fota import router as fota_router
from api.ussd import router as ussd_router
from api.auth import router as auth_router
from api.device import router as device_router

def start_server(lifespan):
    app = FastAPI(lifespan=lifespan)

    # CORS Configuration
    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(fota_router)
    app.include_router(ussd_router)
    app.include_router(auth_router)
    app.include_router(device_router)

    # Define HTTP config - This one manages the lifespan (startup/shutdown events)
    config_http = uvicorn.Config(app, host="0.0.0.0", port=80, log_level="info", lifespan="on")
    server_http = uvicorn.Server(config_http)

    # Define HTTPS config - Lifespan disabled to avoid duplicate tasks/init
    config_https = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=443, 
        log_level="info",
        ssl_keyfile=config.SSL_PRIVKEY_PEM,
        ssl_certfile=config.SSL_FULLCHAIN_PEM,
        lifespan="off"
    )
    server_https = uvicorn.Server(config_https)

    # Async loop to run both
    async def serve():
        await asyncio.gather(
            server_http.serve(),
            server_https.serve(),
        )

    # Run the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(serve())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
