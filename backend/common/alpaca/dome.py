"""Device Alpaca Dome pour le toit roulant.

Correspondances retenues :

| Etat interne | ShutterStatus |
|---|---|
| OPENED            | 0 (Open)    |
| CLOSED            | 1 (Closed)  |
| OPENING           | 2 (Opening) |
| CLOSING           | 3 (Closing) |
| STOPPED / ERROR / UNKNOWN | 4 (Error) |

Un toit roulant n'a ni rotation ni position azimutale : `Azimuth` et
`Altitude` valent 0, et les methodes de rotation renvoient 1024
(NotImplemented). `AtPark` et `AtHome` signifient « toit ferme ».

Toute commande passe par `DomeService`, donc l'interlock monture s'applique
exactement comme sur l'API REST : un refus devient une erreur Alpaca 1035.
"""

import threading

from fastapi import APIRouter, Request

from backend.common.alpaca.errors import (
    INVALID_OPERATION,
    NOT_CONNECTED,
    NOT_IMPLEMENTED,
    AlpacaError,
)
from backend.common.alpaca.protocol import handle, param_bool
from backend.common.constants import VERSION


router = APIRouter()

PREFIX = "/api/v1/dome/0"

NAME = "Toit roulant"
DESCRIPTION = "Toit roulant de l'observatoire (ObservatoryServer)"
DRIVER_INFO = "ObservatoryServer Alpaca Dome"
DRIVER_VERSION = VERSION
INTERFACE_VERSION = 3

SHUTTER_STATUS = {
    "OPENED": 0,
    "CLOSED": 1,
    "OPENING": 2,
    "CLOSING": 3,
}

MOTION_STATES = ("OPENING", "CLOSING")

_connected = True
_connected_lock = threading.Lock()


# -- acces aux services --------------------------------------------------


def _services():
    from backend import container

    return container.get_services()


def _dome():
    return _services().dome


def _check_connected():
    with _connected_lock:
        if not _connected:
            raise AlpacaError(NOT_CONNECTED, "Device non connecte")


def _roof_state():
    return _dome().state.get("state", "UNKNOWN")


def _shutter_status():
    return SHUTTER_STATUS.get(_roof_state(), 4)


# -- etat de connexion ---------------------------------------------------


def _get_connected():
    with _connected_lock:
        return _connected


def _set_connected(params):
    value = param_bool(params, "Connected")

    global _connected
    with _connected_lock:
        _connected = value

    return None


# -- commandes -----------------------------------------------------------


def _command(method):
    """Transforme un resultat de DomeService en reponse Alpaca."""

    def run(params):
        _check_connected()

        result = getattr(_dome(), method)()

        if not result.get("ok"):
            raise AlpacaError(
                INVALID_OPERATION,
                result.get("message") or "Commande refusee par le serveur",
            )

        return None

    return run


def _set_slaved(params):
    # CanSlave = False : le toit ne suit aucune monture.
    param_bool(params, "Slaved")
    raise AlpacaError(INVALID_OPERATION, "Le toit ne peut pas etre asservi (CanSlave = false)")


def _not_implemented(what):
    def run(params):
        raise AlpacaError(NOT_IMPLEMENTED, f"{what} sans objet pour un toit roulant")

    return run


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


@router.get(PREFIX + "/shutterstatus")
async def shutter_status(request: Request):
    def read(params):
        _check_connected()
        return _shutter_status()

    return await handle(request, read)


@router.get(PREFIX + "/atpark")
async def at_park(request: Request):
    def read(params):
        _check_connected()
        return _roof_state() == "CLOSED"

    return await handle(request, read)


@router.get(PREFIX + "/athome")
async def at_home(request: Request):
    def read(params):
        _check_connected()
        return _roof_state() == "CLOSED"

    return await handle(request, read)


@router.get(PREFIX + "/slewing")
async def slewing(request: Request):
    def read(params):
        _check_connected()
        return _roof_state() in MOTION_STATES

    return await handle(request, read)


@router.get(PREFIX + "/azimuth")
async def azimuth(request: Request):
    def read(params):
        _check_connected()
        return 0.0

    return await handle(request, read)


@router.get(PREFIX + "/altitude")
async def altitude(request: Request):
    def read(params):
        _check_connected()
        return 0.0

    return await handle(request, read)


@router.get(PREFIX + "/cansetshutter")
async def can_set_shutter(request: Request):
    return await handle(request, lambda params: True)


@router.get(PREFIX + "/canslave")
async def can_slave(request: Request):
    return await handle(request, lambda params: False)


@router.get(PREFIX + "/cansyncazimuth")
async def can_sync_azimuth(request: Request):
    return await handle(request, lambda params: False)


@router.get(PREFIX + "/slaved")
async def slaved(request: Request):
    return await handle(request, lambda params: False)


@router.put(PREFIX + "/slaved")
async def set_slaved(request: Request):
    return await handle(request, _set_slaved)


# -- methodes ------------------------------------------------------------


@router.put(PREFIX + "/openshutter")
async def open_shutter(request: Request):
    return await handle(request, _command("open"))


@router.put(PREFIX + "/closeshutter")
async def close_shutter(request: Request):
    return await handle(request, _command("close"))


@router.put(PREFIX + "/park")
async def park(request: Request):
    # Pour un toit roulant, « parker » = fermer.
    return await handle(request, _command("close"))


@router.put(PREFIX + "/abortslew")
async def abort_slew(request: Request):
    return await handle(request, _command("stop"))


@router.put(PREFIX + "/findhome")
async def find_home(request: Request):
    return await handle(request, _not_implemented("FindHome"))


@router.put(PREFIX + "/setpark")
async def set_park(request: Request):
    return await handle(request, _not_implemented("SetPark"))


@router.put(PREFIX + "/slewtoazimuth")
async def slew_to_azimuth(request: Request):
    return await handle(request, _not_implemented("SlewToAzimuth"))


@router.put(PREFIX + "/syncstoazimuth")
async def sync_to_azimuth(request: Request):
    return await handle(request, _not_implemented("SyncToAzimuth"))
