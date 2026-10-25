"""Atelier Arduino : generer la configuration, compiler, televerser.

Deroulement d'un televersement :

1. le croquis est copie dans un dossier temporaire (l'installation est en
   lecture seule) et `roof_config.h` y est regenere depuis les reglages ;
2. compilation avec le FQBN choisi, sortie conservee dans un dossier de build ;
3. **suspension de la liaison serie** : avrdude ne peut pas ouvrir COM4 tant
   que le serveur le tient ;
4. televersement, puis reprise de la liaison et lecture de l'etat.

Le toit doit etre immobile. Un televersement coupe le moteur (l'Arduino
redemarre) : le faire pendant un mouvement laisserait le toit s'arreter ou
continuer sans compte rendu.

La compilation et le televersement durent plusieurs dizaines de secondes :
ils tournent dans un thread et l'interface interroge l'avancement.
"""

import shutil
import tempfile
import threading
import time
from pathlib import Path

from backend.arduino import toolchain
from backend.arduino.config_header import build_header
from backend.common import settings_manager
from backend.common.paths import APP_DIR


MAX_OUTPUT_LINES = 500

KEEP_OUTPUT_LINES = 400

SKETCH_NAME = "RoofController"

MOTION_STATES = ("OPENING", "CLOSING")


class WorkshopError(Exception):
    pass


class Job:

    def __init__(self):
        self._lock = threading.Lock()
        self.state = "idle"
        self.action = None
        self.output = []
        self.started = None
        self.finished = None

    def begin(self, action):
        with self._lock:
            self.state = "running"
            self.action = action
            self.output = []
            self.started = time.time()
            self.finished = None

    def append(self, text):
        if not text:
            return

        with self._lock:
            for line in str(text).splitlines():
                self.output.append(line)
            if len(self.output) > MAX_OUTPUT_LINES:
                del self.output[: len(self.output) - KEEP_OUTPUT_LINES]

    def finish(self, state, message=None):
        if message:
            self.append(message)
        with self._lock:
            self.state = state
            self.finished = time.time()

    def snapshot(self):
        with self._lock:
            elapsed = None
            if self.started:
                end = self.finished or time.time()
                elapsed = round(end - self.started, 1)

            return {
                "state": self.state,
                "action": self.action,
                "output": list(self.output),
                "elapsed": elapsed,
            }


class ArduinoWorkshop:

    def __init__(self, dome):
        self.dome = dome
        self.roof = dome.roof
        self.job = Job()
        self._thread = None

    # -- information -----------------------------------------------------

    def upload_port(self, override=None):

        if override:
            return str(override)

        configured = str(settings_manager.get("arduino_upload_port", "") or "").strip()

        return configured or str(settings_manager.get("serial_port", "COM4"))

    def status(self):

        settings = settings_manager.as_dict()
        cli = toolchain.find_cli(settings)

        info = {
            "available": cli is not None,
            "cli": str(cli) if cli else None,
            "version": None,
            "cores": [],
            "ports": [],
            "fqbn": settings.get("arduino_fqbn"),
            "port": self.upload_port(),
            "sketch": (APP_DIR / "firmware" / SKETCH_NAME).is_dir(),
        }

        if cli is not None:
            try:
                info["version"] = toolchain.version(cli)
                info["cores"] = toolchain.cores(cli)
                info["ports"] = toolchain.ports(cli)
            except toolchain.ToolchainError as ex:
                info["error"] = str(ex)

        return info

    def header_preview(self):
        return build_header(settings_manager.as_dict())

    # -- travaux ---------------------------------------------------------

    def busy(self):
        return self.job.state == "running"

    def _start(self, action, function):

        if self.busy():
            raise WorkshopError("Une operation est deja en cours")

        self.job.begin(action)

        self._thread = threading.Thread(
            target=self._run,
            args=(function,),
            name=f"arduino-{action}",
            daemon=True,
        )
        self._thread.start()

    def _run(self, function):

        try:
            function()
        except WorkshopError as ex:
            self.job.finish("error", f"ECHEC : {ex}")
        except toolchain.ToolchainError as ex:
            self.job.finish("error", f"ECHEC : {ex}")
        except Exception as ex:  # pragma: no cover - garde-fou
            self.job.finish("error", f"ECHEC INATTENDU : {ex}")

    def start_compile(self, fqbn=None):
        self._start("compile", lambda: self._compile_only(fqbn))

    def start_upload(self, fqbn=None, port=None):

        state = self.dome.state.get("state")

        if state in MOTION_STATES:
            raise WorkshopError(
                "Le toit est en mouvement : arreter le toit avant de televerser"
            )

        self._start("upload", lambda: self._upload(fqbn, port))

    # -- etapes ----------------------------------------------------------

    def _require_cli(self, settings):

        cli = toolchain.find_cli(settings)

        if cli is None:
            raise WorkshopError(
                "arduino-cli introuvable : verifier l'installation de l'IDE "
                "Arduino, ou renseigner arduino_cli_path"
            )

        return cli

    def _prepare_sketch(self):

        source = APP_DIR / "firmware" / SKETCH_NAME

        if not (source / f"{SKETCH_NAME}.ino").is_file():
            raise WorkshopError(f"Croquis introuvable : {source}")

        work = Path(tempfile.mkdtemp(prefix="observatory_arduino_"))
        sketch = work / SKETCH_NAME

        shutil.copytree(source, sketch)

        (sketch / "roof_config.h").write_text(
            self.header_preview(),
            encoding="utf-8",
        )

        self.job.append(f"Configuration generee : {sketch / 'roof_config.h'}")

        return work, sketch

    def _build(self, cli, fqbn, sketch, work):

        build = work / "build"

        self.job.append(f"Compilation pour {fqbn}")

        code, output = toolchain.run(
            cli,
            ["compile", "--fqbn", fqbn, "--output-dir", str(build), str(sketch)],
            timeout=300,
        )

        self.job.append(output)

        if code != 0:
            raise WorkshopError("compilation echouee (voir la sortie)")

        self.job.append("Compilation reussie")

        return build

    def _compile_only(self, fqbn=None):

        settings = settings_manager.as_dict()
        cli = self._require_cli(settings)
        fqbn = fqbn or settings.get("arduino_fqbn")

        work, sketch = self._prepare_sketch()

        try:
            self._build(cli, fqbn, sketch, work)
        finally:
            shutil.rmtree(work, ignore_errors=True)

        self.job.finish("done", "Termine")

    def _upload(self, fqbn=None, port=None):

        settings = settings_manager.as_dict()
        cli = self._require_cli(settings)

        fqbn = fqbn or settings.get("arduino_fqbn")
        port = self.upload_port(port)

        work, sketch = self._prepare_sketch()

        try:
            build = self._build(cli, fqbn, sketch, work)

            self.job.append(f"Televersement sur {port}")

            self.dome.maintenance = True
            self.roof.pause()

            try:
                code, output = toolchain.run(
                    cli,
                    [
                        "upload",
                        "-p",
                        str(port),
                        "--fqbn",
                        fqbn,
                        "--input-dir",
                        str(build),
                        str(sketch),
                    ],
                    timeout=300,
                )
                self.job.append(output)
            finally:
                self.roof.resume()
                self.dome.maintenance = False

            if code != 0:
                raise WorkshopError(
                    f"televersement echoue sur {port} (port occupe par un "
                    "autre programme ?)"
                )

            self.job.append("Televersement reussi, attente du redemarrage")

            self._confirm_controller()

        finally:
            shutil.rmtree(work, ignore_errors=True)

        self.job.finish("done", "Termine")

    def _confirm_controller(self, attempts=6, delay=2.0):
        """Attend que le controleur reponde apres son redemarrage.

        L'ouverture du port serie remet l'Arduino en route : selon le
        bootloader, il peut rester muet une a deux secondes. Un seul essai
        donnerait l'impression d'un echec alors que tout va bien.
        """

        for attempt in range(attempts):

            try:
                state = self.roof.command("STATUS", timeout=6)
            except Exception as ex:
                self.job.append(
                    f"Controleur pas encore pret ({attempt + 1}/{attempts}) : {ex}"
                )
                time.sleep(delay)
                continue

            self.job.append(f"Controleur repond : {state}")
            return state

        self.job.append("Controleur muet apres televersement (voir la liaison serie)")
        return None
