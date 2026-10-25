"""Chargement et persistance des reglages de l'observatoire.

Source unique de verite : aucun module ne doit plus lire settings.json
directement. Les valeurs sont validees et typees a l'ecriture, afin qu'une
mauvaise saisie ne puisse plus casser l'evaluateur de securite.
"""

import json
import logging
import os
import threading
from copy import deepcopy

from backend.common.paths import CONFIG_DIR


log = logging.getLogger(__name__)

SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Valeurs par defaut. Elles servent de modele de type pour la validation :
# un reglage absent du fichier prend la valeur definie ici.
DEFAULT_SETTINGS = {
    # --- General ---
    "simulation": True,
    "server_port": 11111,
    # Identifiants Alpaca stables : s'ils changent, NINA cree des devices
    # en double dans sa configuration.
    "dome_unique_id": "73397f03-5117-486b-9b64-060cbef21868",
    "safety_unique_id": "02d17a50-6ddd-440d-ac49-702e42e80bde",
    # --- Toit / Arduino ---
    "serial_port": "COM4",
    "baudrate": 115200,
    # Temps de trajet mesure sur l'installation : 47,6 s en ouverture,
    # 47,1 s en fermeture. On arrondit au-dessus (48) pour que l'estimation
    # de position n'atteigne pas 100 % avant la butee reelle.
    "full_travel_time": 48,
    # Doit rester egal a ROOF_MAX_TRAVEL_MS du firmware (50 s) : le
    # controleur est l'autorite, le serveur ne doit pas le devancer.
    "max_travel_time": 50,
    # --- Monture ASCOM ---
    "telescope_driver": "EQMOD_SIM.Telescope",
    "park_timeout": 300,
    "park_grace_seconds": 180,
    # L'agent de sauvegarde peut parquer lui-meme la monture quand la meteo
    # est dangereuse et que personne ne l'a fait. Jamais sur une commande
    # interactive : NINA croirait sa monture encore en suivi.
    "auto_park_mount": False,
    "close_anyway": False,
    "mount_check_mode": "strict",
    "simulation_mount_parked": True,
    # Protege la monture : toit ferme + monture deparquee = collision.
    "guard_mount": True,
    # L'interface web et l'API de commande ne repondent qu'aux clients de la
    # machine locale. Alpaca (/api/v1/...) reste joignable depuis le reseau,
    # pour NINA. A desactiver si l'on veut piloter depuis une tablette.
    "ui_local_only": True,
    # --- Meteo / securite ---
    "max_wind_speed": 60,
    "max_wind_gust": 70,
    "max_rain_probability": 30,
    "max_rain_mm": 0.1,
    "max_cloud_cover": 80,
    "min_temperature": 0.5,
    "lookahead_hours": 1,
    "weather_max_age_minutes": 30,
    "weather_cache_minutes": 30,
    "weather_update_seconds": 600,
    # L'agent qui ferme le toit sur UNSAFE. A ne desactiver que pour un essai
    # supervise : sans lui, plus aucune fermeture automatique.
    "safety_agent_enabled": True,
    # --- Atelier Arduino ---
    # Vide = detection automatique (installation de l'IDE Arduino, PATH).
    "arduino_cli_path": "",
    "arduino_fqbn": "arduino:avr:nano",
    # Vide = utilise serial_port.
    "arduino_upload_port": "",
    # Brochage du controleur.
    "pin_limit_open": 2,
    "pin_limit_closed": 3,
    "pin_bts_rpwm": 5,
    "pin_bts_lpwm": 6,
    "pin_bts_ren": 7,
    "pin_bts_len": 8,
    # Temporisations du firmware, en millisecondes.
    "roof_no_motion_ms": 4000,
    "roof_debounce_ms": 30,
    "roof_direction_dead_ms": 400,
    "roof_ramp_start_ms": 900,
    "roof_ramp_stop_ms": 200,
    # Vitesses (rapport cyclique 0-255).
    "roof_pwm_min": 110,
    "roof_pwm_max": 255,
}

_lock = threading.RLock()
_settings = None


# -- schema de configuration ---------------------------------------------
#
# Une description par reglage, et un groupe pour l'interface web. Ce schema
# est expose par /api/config/schema : l'UI peut ainsi construire ses champs
# et afficher une aide, sans dupliquer la liste des reglages.

SETTING_INFO = {
    # general
    "simulation": ("general", "Mode simulation global : toit et monture virtuels, aucun acces au materiel."),
    "server_port": ("general", "Port HTTP unique (API REST, Alpaca, management)."),
    "dome_unique_id": ("general", "Identifiant Alpaca stable du Dome. Non modifiable : le changer cree un appareil en double dans NINA."),
    "safety_unique_id": ("general", "Identifiant Alpaca stable du SafetyMonitor. Non modifiable."),
    "ui_local_only": ("general", "L'interface web et les commandes ne repondent qu'aux clients de la machine locale."),
    # toit
    "serial_port": ("toit", "Port serie de l'Arduino (par exemple COM4)."),
    "baudrate": ("toit", "Debit de la liaison serie ; doit correspondre au firmware."),
    "full_travel_time": ("toit", "Temps de trajet complet mesure, en secondes (estimation de position)."),
    "max_travel_time": ("toit", "Doit rester egal a ROOF_MAX_TRAVEL_MS du firmware : c'est lui qui tranche."),
    # monture
    "telescope_driver": ("monture", "ProgID ASCOM du driver (EQMOD.Telescope, ou EQMOD_SIM.Telescope pour un essai)."),
    "park_timeout": ("monture", "Delai maximal d'attente d'un parkage, en secondes."),
    "park_grace_seconds": ("monture", "Temps laisse a la monture pour se parquer avant que le toit refuse."),
    "auto_park_mount": ("monture", "L'agent de sauvegarde peut parquer lui-meme la monture. Jamais sur une commande interactive."),
    "close_anyway": ("monture", "Fermer le toit meme si la monture n'est pas parquee. Dangereux, desactive par defaut."),
    "mount_check_mode": ("monture", "strict : refus si la monture n'est pas parquee. disabled : aucune verification."),
    "guard_mount": ("monture", "Parquer la monture si elle est deparquee alors que le toit est ferme, et arreter la fermeture si elle se deparquille en cours."),
    "simulation_mount_parked": ("monture", "Etat de parkage de la monture simulee (mode simulation)."),
    # meteo
    "max_wind_speed": ("meteo", "Vent moyen maximal, en km/h."),
    "max_wind_gust": ("meteo", "Rafale maximale, en km/h."),
    "max_rain_probability": ("meteo", "Probabilite de pluie maximale sur la fenetre, en pourcentage."),
    "max_rain_mm": ("meteo", "Cumul de pluie maximal sur la fenetre, en millimetres."),
    "max_cloud_cover": ("meteo", "Couverture nuageuse maximale, en pourcentage."),
    "min_temperature": ("meteo", "Temperature minimale avant risque de gel, en degres Celsius."),
    "lookahead_hours": ("meteo", "Fenetre de prevision prise en compte, en heures ; on retient le pire cas."),
    "weather_max_age_minutes": ("meteo", "Au-dela, une mesure est perimee et la securite passe UNSAFE."),
    "weather_cache_minutes": ("meteo", "Duree de validite du cache meteo."),
    "weather_update_seconds": ("meteo", "Intervalle de rafraichissement meteo, en secondes."),
    "safety_agent_enabled": ("meteo", "Fermeture automatique du toit quand la meteo est UNSAFE."),
    # atelier
    "arduino_cli_path": ("arduino", "Chemin d'arduino-cli. Vide : detection automatique (IDE Arduino, PATH)."),
    "arduino_fqbn": ("arduino", "Carte cible pour la compilation et le televersement."),
    "arduino_upload_port": ("arduino", "Port de televersement. Vide : utilise serial_port."),
    "pin_limit_open": ("arduino", "Broche du fin de course d'ouverture."),
    "pin_limit_closed": ("arduino", "Broche du fin de course de fermeture."),
    "pin_bts_rpwm": ("arduino", "Broche RPWM du driver BTS7960 (sens + vitesse)."),
    "pin_bts_lpwm": ("arduino", "Broche LPWM du driver BTS7960 (sens + vitesse)."),
    "pin_bts_ren": ("arduino", "Broche R_EN du driver BTS7960."),
    "pin_bts_len": ("arduino", "Broche L_EN du driver BTS7960."),
    "roof_no_motion_ms": ("arduino", "Delai avant defaut si la butee de depart ne se relache pas, en ms."),
    "roof_debounce_ms": ("arduino", "Anti-rebond des fins de course, en ms."),
    "roof_direction_dead_ms": ("arduino", "Temps mort entre deux sens, en ms."),
    "roof_ramp_start_ms": ("arduino", "Duree de la rampe de demarrage, en ms."),
    "roof_ramp_stop_ms": ("arduino", "Duree de la rampe d'arret sur STOP, en ms."),
    "roof_pwm_min": ("arduino", "Rapport cyclique de depart (0-255)."),
    "roof_pwm_max": ("arduino", "Rapport cyclique maximal (0-255)."),
}

SETTING_CHOICES = {
    "mount_check_mode": ("strict", "disabled"),
    "arduino_fqbn": (
        "arduino:avr:nano",
        "arduino:avr:nano:cpu=atmega328old",
        "arduino:avr:uno",
    ),
}

# Identifiants Alpaca : stables par nature. Les modifier cree un appareil en
# double dans NINA, qui perd alors son association avec le toit existant.
# L'API les refuse ; une remise a zero reste possible en editant le fichier
# de configuration a la main.
READ_ONLY_SETTINGS = ("dome_unique_id", "safety_unique_id")

SETTING_GROUPS = ("general", "toit", "monture", "meteo", "arduino")


def _type_name(value):

    if isinstance(value, bool):
        return "bool"

    if isinstance(value, int):
        return "int"

    if isinstance(value, float):
        return "float"

    if isinstance(value, str):
        return "str"

    return "unknown"


def schema():
    """Description typee des reglages, avec valeurs courantes.

    `requires_restart` vaut True partout : les modules metier lisent la
    configuration a l'import. Ce sera affiche tel quel par l'interface.
    """

    current = as_dict()

    items = []

    for key, default in DEFAULT_SETTINGS.items():

        group, description = SETTING_INFO.get(key, ("general", ""))

        item = {
            "key": key,
            "group": group,
            "type": _type_name(default),
            "default": default,
            "value": current.get(key, default),
            "description": description,
            "requires_restart": True,
            "read_only": key in READ_ONLY_SETTINGS,
        }

        if key in SETTING_CHOICES:
            item["choices"] = list(SETTING_CHOICES[key])

        items.append(item)

    return {
        "groups": list(SETTING_GROUPS),
        "settings": items,
    }


def _coerce(key, default, value):
    """Convertit et valide une valeur selon le type de la valeur par defaut."""

    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"{key} : booleen attendu, recu {value!r}")

    if isinstance(default, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} : entier attendu, recu {value!r}")

    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} : nombre attendu, recu {value!r}")

    if isinstance(default, str):
        return str(value)

    raise ValueError(f"{key} : type de reglage non supporte")


def _merge(raw):
    """Complete un dict brut avec les valeurs par defaut manquantes."""

    merged = deepcopy(DEFAULT_SETTINGS)

    for key, value in (raw or {}).items():
        if key not in DEFAULT_SETTINGS:
            # Reglage obsolete (ex. anciens dome_port/safety_port) : ignore
            # mais conserve une trace.
            log.warning("Reglage inconnu ignore : %s", key)
            continue
        try:
            merged[key] = _coerce(key, DEFAULT_SETTINGS[key], value)
        except ValueError as ex:
            log.error("Reglage invalide ignore (%s), valeur par defaut gardee", ex)

    return merged


def load_settings():
    """Charge les reglages, en creant le fichier au besoin."""

    global _settings

    with _lock:
        if not SETTINGS_FILE.exists():
            _settings = deepcopy(DEFAULT_SETTINGS)
            save_settings(_settings)
            return deepcopy(_settings)

        try:
            # utf-8-sig : un fichier enregistre par Notepad commence souvent
            # par un BOM, que `utf-8` refuse. Sans cela, la configuration
            # serait declaree illisible et remplacee par les valeurs par
            # defaut — l'observatoire passerait en simulation sans prevenir.
            with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as ex:
            bad = SETTINGS_FILE.with_suffix(".json.bad")
            log.critical(
                "settings.json illisible (%s) : sauvegarde dans %s et retour "
                "aux valeurs par defaut (simulation activee)",
                ex,
                bad.name,
            )
            try:
                os.replace(SETTINGS_FILE, bad)
            except OSError:
                pass
            _settings = deepcopy(DEFAULT_SETTINGS)
            save_settings(_settings)
            return deepcopy(_settings)

        _settings = _merge(raw)
        return deepcopy(_settings)


def save_settings(settings):
    """Ecrit les reglages de facon atomique (jamais de fichier tronque)."""

    with _lock:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SETTINGS_FILE)


def reload_settings():
    """Relit le fichier depuis le disque (rechargement a chaud)."""

    return load_settings()


def as_dict():
    """Retourne une copie des reglages courants."""

    with _lock:
        if _settings is None:
            load_settings()
        return deepcopy(_settings)


def get(key, default=None):
    """Retourne un reglage brut (compatibilite avec l'ancienne API)."""

    with _lock:
        if _settings is None:
            load_settings()
        return _settings.get(key, default)


def get_int(key, default=0):
    return int(get(key, default))


def get_float(key, default=0.0):
    return float(get(key, default))


def get_bool(key, default=False):
    return bool(get(key, default))


def update_setting(key, value):
    """Valide puis persiste un reglage. Leve KeyError si la cle est inconnue."""

    global _settings

    if key not in DEFAULT_SETTINGS:
        raise KeyError(key)

    if key in READ_ONLY_SETTINGS:
        raise ValueError(
            f"{key} : identifiant stable, non modifiable "
            "(le changer cree un appareil en double dans NINA)"
        )

    validated = _coerce(key, DEFAULT_SETTINGS[key], value)

    with _lock:
        current = as_dict()
        current[key] = validated
        save_settings(current)
        _settings = current
        return deepcopy(current)
