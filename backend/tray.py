"""Icone de notification et supervision du serveur.

L'application installee ne doit pas etre un service Windows : l'acces COM et
ASCOM exige la session de l'utilisateur. C'est donc une tray app qui :

 - lance le serveur en processus enfant (sans fenetre) ;
 - le relance s'il sort en demandant un redemarrage (code 75) ou s'il plante ;
 - ouvre l'interface web dans le navigateur ;
 - affiche l'etat du toit dans l'infobulle et la couleur de l'icone.

Le serveur n'est jamais execute dans le processus de l'icone : un plantage du
serveur ne doit pas emporter l'icone, et un redemarrage doit vraiment repartir
d'un processus neuf (les modules metier lisent la configuration a l'import).
"""

import ctypes
import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from PIL import Image, ImageDraw
import pystray

from backend.common.paths import APP_DIR, LOG_DIR, is_frozen
from backend.common.restart import RESTART_EXIT_CODE, SUPERVISOR_ENV
from backend.common.settings_manager import get_int


log = logging.getLogger(__name__)

POLL_SECONDS = 5.0

RESTART_BACKOFF_SECONDS = 5.0

MUTEX_NAME = "Local\\ObservatoryServerTray"

_mutex = None


COLORS = {
    "starting": (110, 123, 139),
    "closed": (63, 185, 80),
    "opened": (210, 153, 34),
    "moving": (56, 139, 253),
    "error": (248, 81, 73),
}


def _icon_image(color):

    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    red, green, blue = COLORS.get(color, COLORS["starting"])

    # Disque plein.
    draw.ellipse((4, 4, 60, 60), fill=(red, green, blue, 255))

    # Petit toit : deux traits forment un chevron.
    draw.line((16, 38, 32, 24), fill=(15, 20, 26, 255), width=4)
    draw.line((32, 24, 48, 38), fill=(15, 20, 26, 255), width=4)
    draw.line((20, 44, 44, 44), fill=(15, 20, 26, 255), width=3)

    return image


def _single_instance():
    """Empeche deux icones concurrentes, qui se disputeraient le port."""

    global _mutex

    if os.name != "nt":
        return True

    kernel32 = ctypes.windll.kernel32
    _mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)

    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


class Supervisor:

    def __init__(self):
        self.port = get_int("server_port", 11111)
        self.child = None
        self.stopping = False
        self.icon = None
        self.crashes = 0
        self.started_at = 0.0
        self.menu_status = "Démarrage…"

    # -- processus -------------------------------------------------------

    def command(self):

        if is_frozen():
            return [sys.executable, "--server"]

        return [sys.executable, str(APP_DIR / "launcher.py"), "--server"]

    def running(self):
        return self.child is not None and self.child.poll() is None

    def start(self):

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / "server.log"

        environment = os.environ.copy()
        environment[SUPERVISOR_ENV] = "1"

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        with open(log_path, "a", encoding="utf-8", buffering=1) as output:

            self.child = subprocess.Popen(
                self.command(),
                cwd=str(APP_DIR),
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )

        log.info("Serveur lance (pid %s)", self.child.pid)
        self.started_at = time.monotonic()

    def stop(self):

        child = self.child

        if child is None or child.poll() is not None:
            self.child = None
            return

        child.terminate()

        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log.warning("Serveur recalcitrant : arret force")
            child.kill()

        self.child = None

    def restart(self):
        log.info("Redemarrage demande depuis l'icone")
        self.stop()
        time.sleep(0.8)
        self.start()

    # -- surveillance ----------------------------------------------------

    def watch(self):
        """Surveille l'enfant et le relance selon son code de sortie."""

        while not self.stopping:

            child = self.child

            if child is None:
                time.sleep(1.0)
                continue

            started = self.started_at
            code = child.wait()
            uptime = time.monotonic() - started

            if self.stopping:
                return

            self.child = None

            if code == RESTART_EXIT_CODE:
                log.info("Redemarrage demande par le serveur")
                time.sleep(0.8)
                self.start()
                continue

            if code == 0:
                log.info("Serveur arrete normalement : fermeture de l'icone")
                self.quit()
                return

            # Plantage. Un serveur qui tient plus d'une minute remet le
            # compteur a zero : sinon une panne ancienne finirait par
            # interdire toute relance.
            if uptime > 60:
                self.crashes = 0

            self.crashes += 1

            log.error(
                "Serveur termine avec le code %s apres %.0f s (echec %s)",
                code,
                uptime,
                self.crashes,
            )

            if self.crashes >= 5:
                log.critical("Trop d'echecs consecutifs : plus de relance")
                self._set_icon("error", "Observatoire — serveur en échec (voir les journaux)")
                return

            time.sleep(RESTART_BACKOFF_SECONDS)
            self.start()

    # -- etat visuel -----------------------------------------------------

    def _set_icon(self, color, title):

        self.menu_status = title.replace("Observatoire — ", "")

        if self.icon is None:
            return

        try:
            self.icon.icon = _icon_image(color)
            self.icon.title = title
        except Exception:  # pragma: no cover - icon non prete
            pass

    def poll(self):

        url = f"http://127.0.0.1:{self.port}/api/health"

        while not self.stopping:

            try:
                with urllib.request.urlopen(url, timeout=2.0) as response:
                    health = json.loads(response.read().decode("utf-8"))

                dome = health.get("dome") or {}
                state = dome.get("state", "UNKNOWN")
                alarm = dome.get("alarm")

                if alarm:
                    self._set_icon("error", f"Observatoire — {alarm.get('code')}")
                elif state in ("OPENING", "CLOSING"):
                    self._set_icon("moving", f"Observatoire — toit {state.lower()}")
                elif state == "OPENED":
                    self._set_icon("opened", "Observatoire — toit ouvert")
                elif state == "CLOSED":
                    self._set_icon("closed", "Observatoire — toit fermé")
                else:
                    self._set_icon("error", f"Observatoire — toit {state.lower()}")

            except Exception:
                self._set_icon("starting", "Observatoire — serveur injoignable")

            time.sleep(POLL_SECONDS)

    # -- menu ------------------------------------------------------------

    def open_ui(self):
        webbrowser.open(f"http://127.0.0.1:{self.port}/ui/")

    def quit(self):
        self.stopping = True
        self.stop()

        if self.icon is not None:
            self.icon.stop()


def run_tray():

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        filename=str(LOG_DIR / "tray.log"),
        encoding="utf-8",
    )

    if not _single_instance():
        ctypes.windll.user32.MessageBoxW(
            None,
            "ObservatoryServer est déjà en cours d'exécution.\n"
            "Regardez l'icône près de l'horloge.",
            "ObservatoryServer",
            0x40,
        )
        return 0

    supervisor = Supervisor()

    menu = pystray.Menu(
        pystray.MenuItem("Ouvrir l'interface", supervisor.open_ui, default=True),
        pystray.MenuItem(
            lambda item: supervisor.menu_status,
            None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Redémarrer le serveur", supervisor.restart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", supervisor.quit),
    )

    supervisor.icon = pystray.Icon(
        "observatory",
        _icon_image("starting"),
        "Observatoire — démarrage",
        menu,
    )

    supervisor.start()

    threading.Thread(target=supervisor.watch, name="supervisor", daemon=True).start()
    threading.Thread(target=supervisor.poll, name="tray-poll", daemon=True).start()

    log.info("Icone demarree (port %s)", supervisor.port)

    supervisor.icon.run()

    supervisor.quit()

    return 0
