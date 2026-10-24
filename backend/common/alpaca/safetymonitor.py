"""Device Alpaca SafetyMonitor.

Le device expose un seul booleen : `IsSafe`. En cas d'erreur de lecture, on
repond **False** (fail-safe) plutot que de renvoyer une erreur : NINA doit
voir une situation dangereuse, jamais un faux « tout va bien ».
"""

import logging
import threading

from fastapi import APIRouter, Request

from backend.common.alpaca.errors import NOT_CONNECTED, AlpacaError
from backend.common.alpaca.protocol import handle, param_bool
from backend.common.constants import VERSION


log = logging.getLogger(__name__)

router = APIRouter()

PREFIX = "/api/v1/safetymonitor/0"

NAME = "Securite meteo"
DESCRIPTION = "Safety Monitor de l'observatoire (Open-Meteo)"
DRIVER_INFO = "ObservatoryServer Alpaca SafetyMonitor"
DRIVER_VERSION = VERSION
INTERFACE_VERSION = 1

_connected = True
_connected_lock = threading.Lock()
_last_error = None


def _services():
    from backend import container

    return container.get_services()


def _check_connected():
    with _connected_lock:
        if not _connected:
            raise AlpacaError(NOT_CONNECTED, "Device non connecte")


def _get_connected():
    with _connected_lock:
        return _connected


def _set_connected(params):
    value = param_bool(params, "Connected")

    global _connected
    with _connected_lock:
        _connected = value

    return None


def _is_safe(params):
    global _last_error

    _check_connected()

    try:
        safe = bool(_services().safety.is_safe())
    except Exception as ex:
        # Fail-safe : une erreur de lecture ne doit jamais passer pour SAFE.
        if str(ex) != _last_error:
            log.error("Lecture du Safety Monitor impossible : %s", ex)
            _last_error = str(ex)
        return False

    if _last_error is not None:
        log.info("Safety Monitor de nouveau lisible")
        _last_error = None

    return safe


# -- proprietes ----------------------------------------------------------


@router.get(PREFIX + "/connected")
async def get_connected(request: Request):
    return await handle(request, lambda params: _get_connected())


@router.put(PREFIX + "/connected")
async def put_connected(request: Request):
    return await handle(request, _set_connected)


@router.get(PREFIX + "/interfaceversion")
async def interface_version(request: Request):
    return await handle(request, lambda params: INTERFACE_VERSION)


@router.get(PREFIX + "/name")
async def name(request: Request):
    return await handle(request, lambda params: NAME)


@router.get(PREFIX + "/description")
async def description(request: Request):
    return await handle(request, lambda params: DESCRIPTION)


@router.get(PREFIX + "/driverinfo")
async def driver_info(request: Request):
    return await handle(request, lambda params: DRIVER_INFO)


@router.get(PREFIX + "/driverversion")
async def driver_version(request: Request):
    return await handle(request, lambda params: DRIVER_VERSION)


@router.get(PREFIX + "/supportedactions")
async def supported_actions(request: Request):
    return await handle(request, lambda params: [])


@router.get(PREFIX + "/issafe")
async def is_safe(request: Request):
    return await handle(request, _is_safe)
