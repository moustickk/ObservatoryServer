"""Acces a la monture (ASCOM/EQMOD), avec implementation simulee.

Le module dome n'a besoin que de deux informations :
 - la monture est-elle parquee ? (`at_park`)
 - peut-on la parquer ? (`park`)

La phase 4 a deplace ces appels dans un thread COM dedie (`mount.monitor`) :
les methodes d'`AscomMountLink` doivent donc etre appelees depuis ce thread,
qui possede l'appartement COM et garde l'instance du driver ouverte.
"""

import logging
import threading
import time

from backend.mount import driver
from backend.mount.logging import mount_log


log = logging.getLogger(__name__)

try:
    import pythoncom
    import win32com.client
    ASCOM_AVAILABLE = True
except ImportError:  # pragma: no cover - hors Windows
    ASCOM_AVAILABLE = False


class MountLink:
    """Interface commune aux liaisons monture."""

    description = "inconnu"

    @property
    def available(self):
        raise NotImplementedError

    def at_park(self):
        """True / False, ou None si l'etat est indeterminable."""
        raise NotImplementedError

    def park(self, timeout=None):
        raise NotImplementedError


class SimulatedMountLink(MountLink):
    """Monture virtuelle : l'etat de parkage est pilotable."""

    description = "simulation"

    def __init__(self, parked=True):
        self._lock = threading.Lock()
        self._parked = bool(parked)

    @property
    def available(self):
        return True

    def at_park(self):
        with self._lock:
            return self._parked

    def park(self, timeout=None):
        with self._lock:
            self._parked = True
        mount_log("SIMULATION | monture parquee")
        return True

    def set_parked(self, parked):
        """Utilitaire de test."""
        with self._lock:
            self._parked = bool(parked)


class AscomMountLink(MountLink):
    """Pilotage de la monture via le driver ASCOM (EQMOD).

    Cette classe doit etre appelee depuis un thread ayant initialise COM
    (`CoInitialize`) : c'est le cas du thread `mount-com` de `MountMonitor`.
    Elle n'initialise plus COM elle-meme et **conserve** l'instance du driver.

    Conserver l'instance n'est pas un detail : la version precedente ouvrait
    le driver a chaque lecture et le relachait aussitot, si bien que
    `GetActiveObject` ne trouvait plus rien et qu'une **nouvelle** instance
    etait creee toutes les deux secondes. Avec un vrai EQMOD, cela revenait a
    se reconnecter en boucle a la monture.
    """

    CACHE_SECONDS = 2.0
    PROBE_BACKOFF_SECONDS = 5.0

    def __init__(self, driver, park_timeout=300):
        self.driver = driver
        self.park_timeout = float(park_timeout)
        self.description = driver
        self._lock = threading.RLock()
        self._scope = None
        self._at_park = None
        self._at_park_at = 0.0
        self._next_probe = 0.0
        self._last_error = None

    # -- interne ---------------------------------------------------------

    def _connect_scope(self, fresh=False):
        """Ouvre le driver. `fresh=True` force une nouvelle session.

        `GetActiveObject` reutilise l'instance existante — celle de NINA par
        exemple — mais apres une perte de materiel, cette instance peut rester
        bloquee. `DispatchEx` cree une session neuve, ce qui est la seule
        facon de repartir sans redemarrer le serveur.
        """

        if fresh:
            scope = win32com.client.DispatchEx(self.driver)
            mount_log(f"Driver={self.driver} (nouvelle session)")
        else:
            try:
                scope = win32com.client.GetActiveObject(self.driver)
                mount_log(f"Driver={self.driver} (instance existante)")
            except Exception:
                scope = win32com.client.Dispatch(self.driver)
                mount_log(f"Driver={self.driver} (nouvelle instance)")

        if not scope.Connected:
            scope.Connected = True

        return scope

    def _get_scope(self):
        """Instance du driver, conservee entre les lectures."""

        if self._scope is not None:
            try:
                if self._scope.Connected:
                    return self._scope
            except Exception:
                pass

        self._scope = self._connect_scope()
        return self._scope

    def _read_at_park(self):
        if not ASCOM_AVAILABLE:
            raise RuntimeError("pywin32 indisponible")

        scope = self._get_scope()

        # EQMOD peut rester joignable en COM tout en ayant perdu la monture :
        # il repond alors AtPark=False, ce qui ferait croire a un etat valide.
        # On prefere « inconnu » — le toit est refuse dans les deux cas, mais
        # l'operateur voit la vraie panne.
        if not scope.Connected:
            raise RuntimeError("driver ASCOM non connecte")

        return bool(scope.AtPark)

    # -- API -------------------------------------------------------------

    @property
    def available(self):
        return ASCOM_AVAILABLE and self._last_error is None

    @property
    def last_error(self):
        return self._last_error

    def at_park(self):
        with self._lock:
            now = time.monotonic()

            if now < self._next_probe:
                return self._at_park

            if now - self._at_park_at < self.CACHE_SECONDS:
                return self._at_park

            try:
                value = self._read_at_park()
            except Exception as ex:
                self._last_error = str(ex)
                self._at_park = None
                self._next_probe = now + self.PROBE_BACKOFF_SECONDS
                mount_log(f"Monture injoignable : {ex}")
                return None

            self._last_error = None
            self._at_park = value
            self._at_park_at = now
            return value

    def reconnect(self, timeout=15.0):
        """Ferme puis rouvre la liaison au driver, en attendant qu'elle vive.

        Apres un debranchement, EQMOD peut rendre la main avant d'avoir
        reellement reouvert le port de la monture : `Connected` reste faux
        quelques secondes. Un seul essai donnerait un faux echec.
        """

        if not ASCOM_AVAILABLE:
            return False

        with self._lock:

            previous = self._scope
            self._scope = None

            if previous is not None:
                try:
                    previous.Connected = False
                except Exception:
                    pass

                previous = None

                # Laisse le serveur local fermer la session avant d'en ouvrir
                # une neuve.
                time.sleep(1.0)

            self._at_park = None
            self._at_park_at = 0.0
            self._next_probe = 0.0
            self._last_error = None

            try:
                scope = self._connect_scope(fresh=True)
            except Exception as ex:
                self._last_error = str(ex)
                mount_log(f"Reconnexion impossible : {ex}")
                return False

            deadline = time.monotonic() + float(timeout)

            attempt = 0

            while time.monotonic() < deadline:

                try:
                    if scope.Connected:
                        self._scope = scope
                        mount_log("Driver reconnecte")
                        return True
                except Exception as ex:
                    self._last_error = str(ex)

                time.sleep(1.0)
                attempt += 1

                # Toutes les deux secondes, on redemande une instance : un
                # proxy COM peut conserver un etat perime apres la perte du
                # materiel.
                if attempt % 2 == 0:
                    try:
                        scope = self._connect_scope(fresh=True)
                    except Exception as ex:
                        self._last_error = str(ex)

            if not self._last_error:
                self._last_error = (
                    f"driver non connecte apres {float(timeout):.0f} s"
                )

            # Dernier recours : le processus du driver est bloque. EQMOD
            # accepte Connected=True mais ne se connecte jamais ; le tuer et
            # en demarrer un neuf regle le probleme en une seconde.
            if driver.restart(self.driver):

                mount_log("Processus du driver redemarre, nouvelle tentative")

                self._last_error = None

                try:
                    scope = self._connect_scope(fresh=True)
                except Exception as ex:
                    self._last_error = str(ex)
                    return False

                deadline = time.monotonic() + float(timeout)

                while time.monotonic() < deadline:

                    try:
                        if scope.Connected:
                            self._scope = scope
                            mount_log("Driver reconnecte apres redemarrage")
                            return True
                    except Exception as ex:
                        self._last_error = str(ex)

                    time.sleep(1.0)

                if not self._last_error:
                    self._last_error = (
                        "driver non connecte apres redemarrage"
                    )

            mount_log(f"Reconnexion non confirmee : {self._last_error}")
            return False

    def park(self, timeout=None):
        if not ASCOM_AVAILABLE:
            return False

        limit = float(timeout if timeout is not None else self.park_timeout)
        with self._lock:
            try:
                scope = self._get_scope()

                if scope.AtPark:
                    self._at_park = True
                    self._at_park_at = time.monotonic()
                    return True

                mount_log("Envoi de la commande Park()")
                scope.Park()

                deadline = time.monotonic() + limit
                while time.monotonic() < deadline:
                    if scope.AtPark:
                        mount_log("Monture parquee")
                        self._at_park = True
                        self._at_park_at = time.monotonic()
                        return True
                    time.sleep(2)

                mount_log(f"Park() non confirme apres {limit:.0f}s")
                self._at_park = False
                self._at_park_at = time.monotonic()
                return False

            except Exception as ex:
                self._last_error = str(ex)
                self._at_park = None
                self._next_probe = time.monotonic() + self.PROBE_BACKOFF_SECONDS
                mount_log(f"Erreur Park() : {ex}")
                return False


def build_mount_link(settings):
    """Instancie la liaison monture adaptee a la configuration."""

    if settings.get("simulation"):
        log.info("Monture en SIMULATION")
        return SimulatedMountLink(
            parked=settings.get("simulation_mount_parked", True)
        )

    return AscomMountLink(
        settings.get("telescope_driver", "EQMOD_SIM.Telescope"),
        park_timeout=settings.get("park_timeout", 300),
    )
