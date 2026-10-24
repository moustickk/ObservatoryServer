"""Application FastAPI de l'observatoire.

Aucun acces materiel a l'import : tout est construit dans le lifespan via le
conteneur. Le serveur demarre donc meme sans Arduino ni monture.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from backend import container
from backend.common.alpaca.server import router as alpaca_router
from backend.common.config_api import get_config, get_schema
from backend.common.config_update_api import (
    InvalidSettingValue,
    UnknownSetting,
    update_config,
)
from backend.common.constants import APP_NAME, VERSION
from backend.common.health import health_snapshot


log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    services = container.init_services()
    services.start()

    try:
        yield
    finally:
        container.reset_services()


app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    lifespan=lifespan,
)

# Management + Dome + SafetyMonitor, sur le meme port que l'API REST.
app.include_router(alpaca_router)


def _services():
    return container.get_services()


def _command(result):

    if not result.get("ok"):
        log.warning("Commande refusee : %s", result.get("message"))

    status_code = 200 if result.get("ok") else 409

    return JSONResponse(status_code=status_code, content=result)


# -- general -------------------------------------------------------------


@app.get("/")
def root():

    services = _services()

    return {
        "application": APP_NAME,
        "version": VERSION,
        "simulation": services.simulation,
    }


@app.get("/api/health")
def health():
    return health_snapshot(_services())


# -- toit ----------------------------------------------------------------


@app.get("/api/dome/status")
def dome_status():
    return _services().dome.status()


@app.post("/api/dome/open")
def dome_open():
    return _command(_services().dome.open())


@app.post("/api/dome/close")
def dome_close():
    return _command(_services().dome.close())


@app.post("/api/dome/stop")
def dome_stop():
    return _command(_services().dome.stop())


# -- monture -------------------------------------------------------------

@app.post("/api/mount/park")
def mount_park():
    return _command(_services().dome.park_mount())


@app.get("/api/mount/status")
def mount_status():
    return _services().dome.status()["mount"]


# -- securite ------------------------------------------------------------


@app.get("/api/safety/status")
def safety_status():
    return _services().safety.status()


@app.get("/api/safety/device_state")
def safety_device_state():
    return _services().safety.device_state()


# -- configuration -------------------------------------------------------


@app.get("/api/config")
def config():
    return get_config()


@app.get("/api/config/schema")
def config_schema():
    return get_schema()


@app.post("/api/config/{key}/{value}")
def config_update(key: str, value: str):

    try:
        return update_config(key, value)
    except UnknownSetting as ex:
        raise HTTPException(
            status_code=404,
            detail=f"Reglage inconnu : {key}",
        ) from None
    except InvalidSettingValue as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from None
