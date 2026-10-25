"""Tests de l'atelier Arduino (sans materiel)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.arduino import toolchain
from backend.arduino.config_header import build_header
from backend.arduino.workshop import ArduinoWorkshop, Job, WorkshopError
from backend.common import settings_manager


# -- generation de roof_config.h ----------------------------------------


def test_entete_contient_les_valeurs_des_reglages():
    settings = dict(settings_manager.DEFAULT_SETTINGS)
    settings["max_travel_time"] = 42
    settings["pin_limit_open"] = 4
    settings["pin_limit_closed"] = 9
    settings["roof_pwm_min"] = 120
    settings["baudrate"] = 57600

    header = build_header(settings, now=datetime(2026, 10, 25, 12, 30, 0))

    assert "#define ROOF_MAX_TRAVEL_MS    42000UL" in header
    assert "#define PIN_LIMIT_OPEN        4" in header
    assert "#define PIN_LIMIT_CLOSED      9" in header
    assert "#define ROOF_PWM_MIN          120" in header
    assert "#define ROOF_BAUDRATE         57600UL" in header
    assert "25-10-2026 12:30:00" in header
    assert header.startswith("/*")
    assert "#endif" in header


# -- outillage -----------------------------------------------------------


def test_chemin_explicite_absent_est_signale():
    assert toolchain.find_cli({"arduino_cli_path": r"C:\inexistant\arduino-cli.exe"}) is None


def test_chemin_explicite_utilise():
    found = toolchain.find_cli({"arduino_cli_path": r"C:\Windows\System32\cmd.exe"})

    assert found is not None
    assert str(found).endswith("cmd.exe")


def test_lecture_des_ports(monkeypatch):
    payload = {
        "detected_ports": [
            {
                "port": {
                    "address": "COM4",
                    "label": "COM4",
                    "protocol": "serial",
                    "protocol_label": "Serial Port (USB)",
                },
                "matching_boards": [{"name": "Arduino Nano"}],
            }
        ]
    }

    monkeypatch.setattr(
        toolchain,
        "run",
        lambda cli, args, timeout=0: (0, json.dumps(payload)),
    )

    ports = toolchain.ports("cli")

    assert ports == [
        {
            "address": "COM4",
            "label": "COM4",
            "protocol": "Serial Port (USB)",
            "board": "Arduino Nano",
        }
    ]


def test_lecture_des_coeurs(monkeypatch):
    text = "ID          Installé Latest Name\narduino:avr 1.8.8    1.8.8  Arduino AVR Boards\n"

    monkeypatch.setattr(
        toolchain,
        "run",
        lambda cli, args, timeout=0: (0, text),
    )

    cores = toolchain.cores("cli")

    assert cores[0]["id"] == "arduino:avr"
    assert cores[0]["installed"] == "1.8.8"


# -- travaux -------------------------------------------------------------


class FakeRoof:

    def __init__(self):
        self.paused = 0
        self.resumed = 0
        self.commands = []

    def pause(self):
        self.paused += 1

    def resume(self):
        self.resumed += 1

    def command(self, name, timeout=5):
        self.commands.append(name)
        return "CLOSED"


class FakeState:

    def __init__(self, state="CLOSED"):
        self.value = state

    def get(self, key, default=None):
        return self.value if key == "state" else default


class FakeDome:

    def __init__(self, state="CLOSED"):
        self.state = FakeState(state)
        self.roof = FakeRoof()
        self.maintenance = False


def test_le_travail_capture_la_sortie():
    job = Job()

    job.begin("compile")
    assert job.snapshot()["state"] == "running"

    job.append("ligne 1\nligne 2")
    job.finish("done", "Termine")

    snapshot = job.snapshot()

    assert snapshot["state"] == "done"
    assert "ligne 1" in snapshot["output"]
    assert "ligne 2" in snapshot["output"]
    assert snapshot["output"][-1] == "Termine"


def test_le_controleur_est_attendu_apres_redemarrage(monkeypatch):
    """L'Arduino redemarre : les premiers STATUS peuvent echouer."""

    dome = FakeDome(state="CLOSED")
    workshop = ArduinoWorkshop(dome)

    failures = {"count": 2}

    class SlowRoof:
        def command(self, name, timeout=6):
            if failures["count"] > 0:
                failures["count"] -= 1
                raise RuntimeError("muet")
            return "CLOSED"

    workshop.roof = SlowRoof()

    monkeypatch.setattr("backend.arduino.workshop.time.sleep", lambda seconds: None)

    assert workshop._confirm_controller(attempts=6, delay=0) == "CLOSED"
    assert any("pas encore pret" in line for line in workshop.job.snapshot()["output"])


def test_televersement_refuse_si_le_toit_bouge():
    dome = FakeDome(state="OPENING")
    workshop = ArduinoWorkshop(dome)

    with pytest.raises(WorkshopError) as caught:
        workshop.start_upload()

    assert "mouvement" in str(caught.value)
    assert dome.roof.paused == 0
    assert workshop.job.state == "idle"


def test_un_seul_travail_a_la_fois():
    dome = FakeDome(state="CLOSED")
    workshop = ArduinoWorkshop(dome)

    workshop.job.begin("compile")

    with pytest.raises(WorkshopError):
        workshop.start_compile()


def test_le_televersement_suspend_et_reprend_la_liaison(monkeypatch):
    """Verifie l'ordre : compilation, pause, upload, reprise."""

    dome = FakeDome(state="CLOSED")
    workshop = ArduinoWorkshop(dome)

    calls = []

    monkeypatch.setattr(workshop, "_prepare_sketch", lambda: (Path("."), Path(".")))
    monkeypatch.setattr(
        workshop,
        "_build",
        lambda cli, fqbn, sketch, work: (calls.append("compile"), Path("build"))[1],
    )
    monkeypatch.setattr(
        toolchain,
        "find_cli",
        lambda settings=None: Path("C:/arduino-cli.exe"),
    )
    monkeypatch.setattr(
        toolchain,
        "run",
        lambda cli, args, timeout=0: (calls.append("upload"), (0, "ok"))[1],
    )
    monkeypatch.setattr(
        "backend.arduino.workshop.shutil.rmtree",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("backend.arduino.workshop.time.sleep", lambda seconds: None)

    workshop._run(lambda: workshop._upload("arduino:avr:nano", "COM4"))

    assert calls == ["compile", "upload"]
    assert dome.roof.paused == 1
    assert dome.roof.resumed == 1
    assert dome.maintenance is False
    assert workshop.job.state == "done"
