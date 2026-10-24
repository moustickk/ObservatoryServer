"""Mise a jour des reglages, avec validation.

Les valeurs sont desormais typees d'apres settings_manager : impossible
d'ecrire une chaine dans max_wind_speed et de casser l'evaluateur.
"""

from backend.common.settings_manager import update_setting


class UnknownSetting(KeyError):
    pass


class InvalidSettingValue(ValueError):
    pass


def update_config(key, value):

    try:
        settings = update_setting(key, value)
    except KeyError:
        raise UnknownSetting(key)
    except ValueError as ex:
        raise InvalidSettingValue(str(ex))

    return {
        "key": key,
        "value": settings[key],
        "requires_restart": True,
        "settings": settings,
    }
