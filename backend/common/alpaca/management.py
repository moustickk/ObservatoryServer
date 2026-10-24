"""API de management Alpaca.

C'est ce que NINA interroge en premier pour decouvrir les devices exposes par
le serveur, puis pour verifier la version d'API supportee.
"""

from fastapi import APIRouter, Request

from backend.common.alpaca.protocol import handle
from backend.common.constants import APP_NAME, VERSION


router = APIRouter()

API_VERSION = 3

MANUFACTURER = "ObservatoryServer"
LOCATION = "Observatoire"


def _services():
    # Import local : le conteneur construit les services au demarrage, jamais
    # a l'import (et il ne doit pas y avoir de cycle d'import).
    from backend import container

    return container.get_services()


@router.get("/management/v1/apiversions")
async def api_versions(request: Request):
    return await handle(request, lambda params: [API_VERSION])


@router.get("/management/v1/description")
async def description(request: Request):
    return await handle(
        request,
        lambda params: {
            "ServerName": APP_NAME,
            "Manufacturer": MANUFACTURER,
            "ManufacturerVersion": VERSION,
            "Location": LOCATION,
        },
    )


@router.get("/management/v1/configureddevices")
async def configured_devices(request: Request):
    services = _services()

    dome_id = services.settings.get("dome_unique_id", "")
    safety_id = services.settings.get("safety_unique_id", "")

    return await handle(
        request,
        lambda params: [
            {
                "DeviceName": "Toit roulant",
                "DeviceType": "Dome",
                "DeviceNumber": 0,
                "UniqueID": dome_id,
            },
            {
                "DeviceName": "Securite meteo",
                "DeviceType": "SafetyMonitor",
                "DeviceNumber": 0,
                "UniqueID": safety_id,
            },
        ],
    )
