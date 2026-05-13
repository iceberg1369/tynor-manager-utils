import asyncio
import copy
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import config
from api.fota import router as fota_router
from api.ussd_parser import router as ussd_router
from api.auth import router as auth_router
from api.device import router as device_router


class IgnoreInvalidHttpFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "Invalid HTTP request received." not in record.getMessage()


LOG_CONFIG = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
LOG_CONFIG.setdefault("filters", {})
LOG_CONFIG["filters"]["ignore_invalid_http"] = {"()": IgnoreInvalidHttpFilter}
LOG_CONFIG["loggers"]["uvicorn.error"].setdefault("filters", [])
LOG_CONFIG["loggers"]["uvicorn.error"]["filters"].append("ignore_invalid_http")


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
    config_http = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=80,
        log_level="info",
        lifespan="on",
        access_log=False,
        log_config=LOG_CONFIG,
    )
    server_http = uvicorn.Server(config_http)

    ssl_certfile = getattr(config, "SSL_FULLCHAIN_PEM", None)
    ssl_keyfile = getattr(config, "SSL_PRIVKEY_PEM", None)

    servers = [server_http]
    if ssl_certfile and ssl_keyfile:
        # Define HTTPS config - Lifespan disabled to avoid duplicate tasks/init
        config_https = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=443,
            log_level="info",
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            lifespan="off",
            access_log=False,
            log_config=LOG_CONFIG,
        )
        servers.append(uvicorn.Server(config_https))
    else:
        print("⚠️ SSL cert/key not configured; HTTPS server disabled.")

    # Async loop to run both
    async def serve():
        await asyncio.gather(*(server.serve() for server in servers))

    # Run the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(serve())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
