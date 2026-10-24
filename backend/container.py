"""Conteneur de services, construit une seule fois au demarrage.

Aucun module ne doit ouvrir de port serie ou COM a l'import : c'est le
conteneur (donc le lifespan FastAPI) qui instancie le materiel.

Deux threads sont proprietaires du materiel :

 - `RoofController` : seul a parler au port serie du toit ;
 - `MountMonitor`   : seul a appeler le driver ASCOM de la monture.

Tout le reste (API REST, Alpaca, agent de sauvegarde) ne lit que leurs caches.
"""

import logging
import threading

from backend.common import settings_manager
from backend.common.alpaca.discovery import DiscoveryResponder
from backend.dome.controller import RoofController
from backend.dome.monitor import start_monitor
from backend.dome.serial_link import build_roof_link
from backend.dome.service import DomeService
from backend.mount.link import build_mount_link
from backend.mount.monitor import MountMonitor
from backend.safety.agent import BackupAgent
from backend.safety.monitor import weather_monitor
from backend.safety.service import SafetyService


log = logging.getLogger(__name__)

_lock = threading.Lock()
_services = None


class Services:

    def __init__(self):
        self.settings = settings_manager.load_settings()
        self.simulation = bool(self.settings.get("simulation"))
        self.stop_event = threading.Event()

        self.roof_link = build_roof_link(self.settings)
        self.roof = RoofController(self.roof_link)

        self.mount_link = build_mount_link(self.settings)
        self.mount = MountMonitor(self.mount_link)

        self.dome = DomeService(self.roof, self.mount, self.settings)
        self.safety = SafetyService()

        self.agent = BackupAgent(
            self.dome,
            self.safety,
            self.settings,
            self.stop_event,
        )

        self.discovery = DiscoveryResponder(
            alpaca_port=self.settings.get("server_port", 11111)
        )

        self.threads = []

    def start(self):
        # Le materiel d'abord : les caches doivent se remplir avant que
        # l'API ne reponde.
        self.roof.start()
        self.mount.start()

        self.discovery.start()

        self.threads.append(start_monitor(self.dome, self.stop_event))

        agent_thread = self.agent.start()
        if agent_thread is not None:
            self.threads.append(agent_thread)

        weather = threading.Thread(
            target=weather_monitor,
            args=(self.stop_event,),
            name="weather-monitor",
            daemon=True,
        )
        weather.start()
        self.threads.append(weather)

        log.info(
            "Services demarres | simulation=%s | toit=%s | monture=%s",
            self.simulation,
            self.roof_link.description,
            self.mount_link.description,
        )

    def stop(self):
        self.stop_event.set()
        self.discovery.stop()

        # Arreter les producteurs de donnees avant de fermer la liaison.
        self.mount.stop()
        self.roof.close()

        log.info("Services arretes")


def init_services():
    global _services

    with _lock:
        if _services is None:
            _services = Services()
        return _services


def get_services():
    if _services is None:
        raise RuntimeError("Services non initialises (lifespan non demarre)")
    return _services


def reset_services():
    """Fermer et oublier les services courants (tests, rechargement)."""

    global _services

    with _lock:
        if _services is not None:
            _services.stop()
        _services = None
