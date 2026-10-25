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
from backend.arduino.workshop import WorkshopError
from backend.common import settings_manager
from backend.common.autostart import is_enabled as autostart_enabled
from backend.common.autostart import set_enabled_threaded, shortcut_path
from backend.common.restart import schedule_restart
from backend.mount.drivers import list_drivers
from backend.common.alpaca.server import router as alpaca_router
from backend.common.config_api import get_config, get_schema
from backend.common.config_update_api import (
    InvalidSettingValue,
    UnknownSetting,
    update_config,
)
from backend.common.constants import APP_NAME, VERSION
from backend.common.docs_api import UnknownDocument, list_documents, render
from backend.common.health import health_snapshot
from backend.common.logs_api import UnknownLog, list_logs, tail_log


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

    response = await call_next(request)

    # Les fichiers de l'interface changent a chaque mise a jour. Sans cette
    # consigne, le navigateur peut reutiliser un app.js ancien sans revalider :
    # le bouton existe dans le HTML mais son code est absent, et la fonction
    # semble ne pas marcher. `no-cache` force la revalidation (ETag court).
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-cache"

    return response


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


@app.post("/api/server/restart")
def server_restart():
    """Relance le serveur pour appliquer la configuration.

    Refuse si le toit bouge : couper la liaison au milieu d'un trajet laisse
    le firmware seul maitre du mouvement, sans que le serveur puisse en
    rendre compte.
    """

    state = _services().dome.state.get("state")

    if state in ("OPENING", "CLOSING"):
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "message": f"Toit en mouvement ({state}) : redemarrage refuse",
            },
        )

    schedule_restart(settings_manager.get_int("server_port", 11111))

    return JSONResponse(
        status_code=202,
        content={"ok": True, "message": "redemarrage programme"},
    )


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


@app.get("/api/mount/drivers")
def mount_drivers():
    """Pilotes ASCOM de monture installes, pour le selecteur de l'interface."""

    drivers = list_drivers()

    return {
        "count": len(drivers),
        "drivers": drivers,
        "current": settings_manager.get("telescope_driver", ""),
    }


# -- journaux ------------------------------------------------------------

@app.get("/api/logs")
def logs_list():
    return {"logs": list_logs()}


@app.get("/api/logs/{name}")
def logs_tail(name: str, lines: int = 200):

    try:
        content, size, truncated = tail_log(name, lines)
    except UnknownLog:
        raise HTTPException(status_code=404, detail=f"Journal inconnu : {name}") from None

    return {
        "name": name,
        "lines": content,
        "size": size,
        "truncated": truncated,
    }


# -- systeme -------------------------------------------------------------

@app.get("/api/system/autostart")
def autostart_status():
    return {
        "enabled": autostart_enabled(),
        "path": str(shortcut_path()),
    }


@app.post("/api/system/autostart")
def autostart_set(enabled: bool):

    try:
        state = set_enabled_threaded(enabled)
    except Exception as ex:
        return JSONResponse(
            status_code=500,
            content={
                "enabled": autostart_enabled(),
                "message": f"Modification impossible : {ex}",
            },
        )

    return {"enabled": state}


# -- documentation -------------------------------------------------------

@app.get("/api/docs")
def docs_list():
    return {"documents": list_documents()}


@app.get("/api/docs/{name}")
def docs_render(name: str):

    try:
        return render(name)
    except UnknownDocument:
        raise HTTPException(status_code=404, detail=f"Document inconnu : {name}") from None


# -- atelier Arduino -----------------------------------------------------

@app.get("/api/arduino/status")
def arduino_status():
    return _services().workshop.status()


@app.get("/api/arduino/header")
def arduino_header():
    return {"header": _services().workshop.header_preview()}


@app.get("/api/arduino/job")
def arduino_job():
    return _services().workshop.job.snapshot()


@app.post("/api/arduino/compile")
def arduino_compile(fqbn: str | None = None):

    try:
        _services().workshop.start_compile(fqbn)
    except WorkshopError as ex:
        return JSONResponse(status_code=409, content={"message": str(ex)})

    return JSONResponse(status_code=202, content={"ok": True})


@app.post("/api/arduino/upload")
def arduino_upload(fqbn: str | None = None, port: str | None = None):

    try:
        _services().workshop.start_upload(fqbn, port)
    except WorkshopError as ex:
        return JSONResponse(status_code=409, content={"message": str(ex)})

    return JSONResponse(status_code=202, content={"ok": True})


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
