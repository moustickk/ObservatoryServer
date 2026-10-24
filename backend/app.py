"""Application FastAPI de l'observatoire.

Aucun acces materiel a l'import : tout est construit dans le lifespan via le
conteneur. Le serveur demarre donc meme sans Arduino ni monture.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import container
from backend.common import settings_manager
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

# Interface web locale, servie par le meme serveur : aucune installation
# supplementaire, aucun acces reseau externe.
WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/ui", StaticFiles(directory=WEB_DIR, html=True), name="ui")


# -- acces local ----------------------------------------------------------
#
# L'interface et les commandes du toit ne doivent pas etre accessibles a
# n'importe qui sur le reseau : /api/dome/open ouvre un toit. Les routes
# Alpaca (/api/v1/...) restent ouvertes, sinon NINA ne pourrait plus
# commander l'observatoire depuis une autre machine.

LOCAL_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}

LOCAL_ONLY_PREFIXES = ("/ui", "/docs", "/redoc", "/openapi.json")


def requires_local_client(path):
    if path.startswith("/api/v1/"):
        return False

    if path.startswith("/api/"):
        return True

    return path.startswith(LOCAL_ONLY_PREFIXES)


@app.middleware("http")
async def local_only_ui(request: Request, call_next):
    if (
        settings_manager.get("ui_local_only", True)
        and requires_local_client(request.url.path)
    ):
        host = request.client.host if request.client else None

        if host not in LOCAL_HOSTS:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Interface locale uniquement (ui_local_only)",
                },
            )

    return await call_next(request)


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
        "ui": "/ui/",
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
