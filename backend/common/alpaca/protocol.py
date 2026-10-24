"""Protocole HTTP commun a tous les devices Alpaca.

Chaque reponse est enveloppee dans la structure imposee par Alpaca :

    {
      "Value": ...,
      "ClientTransactionID": n,
      "ServerTransactionID": n,
      "ErrorNumber": n,
      "ErrorMessage": "..."
    }

Les parametres arrivent soit dans la chaine de requete (GET), soit dans un
corps `application/x-www-form-urlencoded` (PUT). On accepte les deux, sans
dependre de python-multipart.
"""

import logging
import threading
from urllib.parse import parse_qs

from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.common.alpaca.errors import (
    DRIVER_ERROR,
    INVALID_VALUE,
    AlpacaError,
)


log = logging.getLogger(__name__)

_tx_lock = threading.Lock()
_tx_counter = 0


def next_transaction_id():
    """Identifiant de transaction serveur, strictement croissant."""

    global _tx_counter

    with _tx_lock:
        _tx_counter += 1
        return _tx_counter


async def read_params(request):
    """Fusionne les parametres de la requete (query string + formulaire)."""

    params = {key: value for key, value in request.query_params.items()}

    try:
        body = await request.body()
    except Exception:
        body = b""

    if body:
        try:
            text = body.decode("utf-8", errors="replace")
            for key, values in parse_qs(text, keep_blank_values=True).items():
                if values:
                    params[key] = values[0]
        except Exception:
            # Un corps illisible ne doit pas faire tomber la requete : les
            # champs manquants seront signales par la validation.
            log.debug("Corps de requete Alpaca illisible, ignore")

    return params


def _client_transaction_id(params):
    try:
        return int(params.get("ClientTransactionID", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _envelope(value, client_tx, error_number=0, error_message=""):
    return {
        "Value": value,
        "ClientTransactionID": int(client_tx),
        "ServerTransactionID": next_transaction_id(),
        "ErrorNumber": int(error_number),
        "ErrorMessage": error_message,
    }


def _error_response(error, client_tx):
    body = _envelope(None, client_tx, error.number, error.message)

    if error.number != INVALID_VALUE:
        log.warning("Alpaca %s : %s", error.number, error.message)

    return JSONResponse(status_code=error.http_status, content=body)


async def handle(request, fn, params=None):
    """Execute `fn(params)` hors boucle asyncio et renvoie l'enveloppe."""

    if params is None:
        params = await read_params(request)

    client_tx = _client_transaction_id(params)

    try:
        value = await run_in_threadpool(fn, params)
    except AlpacaError as ex:
        return _error_response(ex, client_tx)
    except Exception as ex:  # pragma: no cover - filet de securite
        log.exception("Erreur non geree dans un appel Alpaca")
        return _error_response(AlpacaError(DRIVER_ERROR, str(ex)), client_tx)

    return _envelope(value, client_tx)


# -- lecture / validation des parametres ---------------------------------


def param_bool(params, name, required=True):
    """Lit un booleen de formulaire (true/1/yes/on et l'inverse)."""

    if name not in params or params[name] is None:
        if required:
            raise AlpacaError(INVALID_VALUE, f"Parametre manquant : {name}")
        return None

    text = str(params[name]).strip().lower()

    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False

    raise AlpacaError(INVALID_VALUE, f"{name} : booleen attendu, recu {params[name]!r}")


def param_float(params, name, required=True):
    """Lit un flottant de formulaire."""

    if name not in params or params[name] is None:
        if required:
            raise AlpacaError(INVALID_VALUE, f"Parametre manquant : {name}")
        return None

    try:
        return float(params[name])
    except (TypeError, ValueError):
        raise AlpacaError(
            INVALID_VALUE, f"{name} : nombre attendu, recu {params[name]!r}"
        ) from None
