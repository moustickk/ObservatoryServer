from contextlib import asynccontextmanager
import threading

from fastapi import FastAPI

from backend.dome.start_monitor import (
    start_monitor
)

from backend.common.health_api import (
    get_health
)

from backend.common.config_update_api import (
    update_config
)

from backend.common.config_api import (
    get_config
)

from backend.safety.service import (
    SafetyService
)

from backend.safety.monitor import (
    weather_monitor
)

from backend.dome.api import (
    get_status as get_dome_status
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    threading.Thread(
        target=weather_monitor,
        daemon=True
    ).start()

    start_monitor()

    yield


app = FastAPI(
    lifespan=lifespan
)

safety = SafetyService()


@app.get("/")
def root():

    return {
        "application": "ObservatoryServer",
        "version": "3.0.0-alpha"
    }


@app.get("/api/safety/status")
def safety_status():

    return safety.status()


@app.get("/api/safety/device_state")
def safety_device_state():

    return safety.device_state()


@app.get("/api/dome/status")
def dome_status():

    return get_dome_status()


@app.get("/api/config")
def config():

    return get_config()


@app.post("/api/config/{key}/{value}")
def config_update(
    key: str,
    value: str
):

    return update_config(
        key,
        value
    )


@app.get("/api/health")
def health():

    return get_health()