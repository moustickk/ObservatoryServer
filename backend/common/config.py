"""Facade d'acces aux reglages.

Conserve l'API historique (`get`) utilisee par les modules metier, mais
s'appuie desormais sur settings_manager (validation + persistance atomique).
"""

from backend.common.settings_manager import (
    as_dict,
    get,
    get_bool,
    get_float,
    get_int,
    load_settings,
    reload_settings,
    update_setting,
)

__all__ = [
    "as_dict",
    "get",
    "get_bool",
    "get_float",
    "get_int",
    "load_settings",
    "reload_settings",
    "update_setting",
]
