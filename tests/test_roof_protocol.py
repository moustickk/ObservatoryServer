"""Tests du protocole serie du firmware et des regles de la liaison toit.

Aucun materiel n'est necessaire : ces tests exercent l'analyse des reponses,
la liaison serie (avec un port factice) et la machine a etats simulee, qui
reproduit les regles visibles du firmware.

Lancer avec :

    .\\.venv\\Scripts\\python.exe -m pytest
"""

import threading
import time

import pytest

from backend.dome.serial_link import (
    CommandRejected,
    LinkError,
    SerialRoofLink,
    SimulatedRoofLink,
    build_roof_link,
    parse_response,
    parse_state,
)


# -- analyse des messages -------------------------------------------------


@pytest.mark.parametrize(
    "line, expected",
    [
        ("OK:CLOSED", "CLOSED"),
        ("OK:OPENING", "OPENING"),
        ("ER:BUSY:OPENING", "OPENING"),
        ("ER:FAULT:ERROR", "ERROR"),
        ("EVT:BOOT:CLOSED", "CLOSED"),
        ("EVT:TIMEOUT:ERROR", "ERROR"),
        ("EVT:NO_MOTION:ERROR", "ERROR"),
        ("OK:UNKNOWN", "UNKNOWN"),
        # insensible a la casse
        ("ok:closed", "CLOSED"),
        # ligne vide ou sans etat
        ("", None),
        ("OK:", None),
        ("bruit serie", None),
    ],
)
def test_parse_state(line, expected):
    assert parse_state(line) == expected


def test_parse_response_ok():
    assert parse_response("OK:CLOSED") == ("ok", None, "CLOSED")


def test_parse_response_error():
    assert parse_response("ER:BUSY:CLOSING") == ("error", "BUSY", "CLOSING")


def test_parse_response_error_sans_etat():
    assert parse_response("ER:UNKNOWN_CMD") == ("error", "UNKNOWN_CMD", None)


@pytest.mark.parametrize("line", ["EVT:BOOT:CLOSED", "CLOSED", "bruit", ""])
def test_parse_response_ignore_le_reste(line):
    assert parse_response(line) is None


# -- liaison serie, avec un port factice ----------------------------------


class FakeSerial:
    """Port serie factice : rend les lignes preparees, enregistre les ecritures."""

    def __init__(self, lines=()):
        self.lines = list(lines)
        self.written = []
        self.timeout = 1.0
        self.is_open = True

    def write(self, data):
        self.written.append(data)

    def flush(self):
        pass

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def close(self):
        self.is_open = False


def make_link(*lines):
    link = object.__new__(SerialRoofLink)
    link.port = "TEST"
    link.baudrate = 115200
    link.description = "test"
    link._lock = threading.RLock()
    link._ser = FakeSerial([line.encode() + b"\n" for line in lines])
    link._last_error = None
    link._last_attempt = 0.0
    return link


def test_serial_envoie_la_commande_et_lit_letat():
    link = make_link("OK:OPENING")
    assert link.send("OPEN") == "OPENING"
    assert link._ser.written == [b"OPEN\n"]


def test_serial_ignore_les_evenements_asynchrones():
    """Un EVT: arrivant pendant l'attente ne doit pas etre pris pour la reponse."""

    link = make_link("EVT:OPENED:OPENED", "OK:STOPPED")
    assert link.send("STOP") == "STOPPED"


def test_serial_traduit_un_refus_en_CommandRejected():
    link = make_link("ER:BUSY:CLOSING")

    with pytest.raises(CommandRejected) as caught:
        link.send("OPEN")

    assert caught.value.code == "BUSY"
    assert caught.value.state == "CLOSING"
    # Un refus n'est pas une panne : le lien reste ouvert.
    assert link.connected


def test_serial_signale_un_firmware_trop_ancien():
    """Ancien protocole : un etat nu, sans prefixe OK:/ER:."""

    link = make_link("CLOSED")

    with pytest.raises(LinkError) as caught:
        link.send("STATUS")

    assert "reflasher" in str(caught.value)


def test_serial_sans_reponse_leve_LinkError():
    link = make_link()

    with pytest.raises(LinkError):
        link.send("STATUS")


# -- machine a etats simulee (regles du firmware) -------------------------


def test_simulation_inversion_refusee_sans_arret():
    link = SimulatedRoofLink(travel_time=0.05, max_travel_time=0.2)

    assert link.send("OPEN") == "OPENING"
    assert link.send("OPEN") == "OPENING"  # idempotent

    with pytest.raises(CommandRejected) as caught:
        link.send("CLOSE")
    assert caught.value.code == "BUSY"

    assert link.send("STOP") == "STOPPED"
    assert link.send("CLOSE") == "CLOSING"


def test_simulation_arret_fige_la_position():
    link = SimulatedRoofLink(travel_time=0.05, max_travel_time=0.2)

    link.send("OPEN")
    assert link.send("STOP") == "STOPPED"

    time.sleep(0.08)
    # Sans STOP, le toit serait OPENED depuis longtemps.
    assert link.send("STATUS") == "STOPPED"


def test_simulation_arrivee_sur_butee():
    link = SimulatedRoofLink(travel_time=0.02, max_travel_time=0.2)

    link.send("OPEN")
    time.sleep(0.04)
    assert link.send("STATUS") == "OPENED"

    link.send("CLOSE")
    time.sleep(0.04)
    assert link.send("STATUS") == "CLOSED"


def test_simulation_depassement_du_temps_de_trajet():
    link = SimulatedRoofLink(travel_time=45, max_travel_time=60)

    link.send("OPEN")
    link._motion_start = time.time() - 61

    assert link.send("STATUS") == "ERROR"

    with pytest.raises(CommandRejected) as caught:
        link.send("CLOSE")
    assert caught.value.code == "FAULT"

    # STOP est la seule commande qui acquitte le defaut.
    assert link.send("STOP") == "STOPPED"
    assert link.send("CLOSE") == "CLOSING"


def test_simulation_commande_inconnue():
    link = SimulatedRoofLink()

    with pytest.raises(CommandRejected) as caught:
        link.send("OUVRE")

    assert caught.value.code == "UNKNOWN_CMD"
    assert caught.value.state == "CLOSED"


# -- integration avec DomeService ----------------------------------------


class StubMount:
    description = "monture de test"
    available = True

    def __init__(self, at_park=True):
        self._at_park = at_park

    def at_park(self):
        return self._at_park


class RefusingRoof:
    description = "controleur de test"
    connected = True

    def __init__(self, error):
        self.error = error
        self.commands = []

    def send(self, command, timeout=2.0):
        self.commands.append(command)
        raise self.error


@pytest.fixture
def build_dome(monkeypatch, tmp_path):
    """DomeService isole : ni fichier d'etat ni journal sur le disque."""

    monkeypatch.setattr("backend.common.state.STATE_FILE", tmp_path / "roof_state.json")
    monkeypatch.setattr("backend.dome.service.log_open", lambda: None)
    monkeypatch.setattr("backend.dome.service.log_close", lambda: None)
    monkeypatch.setattr("backend.dome.service.log_stop", lambda: None)

    def build(roof, mount=None):
        from backend.dome.service import DomeService

        return DomeService(roof, mount or StubMount(), {"full_travel_time": 45})

    return build


def test_refus_de_defaut_est_une_alarme(build_dome):
    dome = build_dome(RefusingRoof(CommandRejected("FAULT", "ERROR")))

    result = dome.open()

    assert result["ok"] is False
    assert result["code"] == "FAULT"
    assert result["state"] == "ERROR"
    assert dome.state.alarm["code"] == "ROOF_FAULT"


def test_refus_busy_nest_pas_une_alarme(build_dome):
    dome = build_dome(RefusingRoof(CommandRejected("BUSY", "CLOSING")))
    dome.state.set_state("CLOSING")

    result = dome.open()

    assert result["ok"] is False
    assert result["code"] == "BUSY"
    assert result["state"] == "CLOSING"
    assert dome.state.alarm is None


def test_panne_de_liaison_reste_une_alarme(build_dome):
    dome = build_dome(RefusingRoof(LinkError("port disparu")))

    result = dome.open()

    assert result["ok"] is False
    assert result["code"] == "ROOF_LINK"
    assert result["state"] == "UNKNOWN"
    assert dome.state.alarm["code"] == "ROOF_LINK"


def test_interlock_prime_sur_le_controleur(build_dome):
    roof = RefusingRoof(LinkError("ne doit pas etre appele"))
    dome = build_dome(roof, mount=StubMount(at_park=False))

    result = dome.open()

    assert result["ok"] is False
    assert result["code"] == "MOUNT_NOT_PARKED"
    assert roof.commands == []  # aucune commande n'a atteint le controleur


# -- construction ---------------------------------------------------------


def test_build_simulation_utilise_les_delais_de_la_configuration():
    link = build_roof_link(
        {
            "simulation": True,
            "full_travel_time": 45,
            "max_travel_time": 60,
        }
    )

    assert isinstance(link, SimulatedRoofLink)
    assert link.travel_time == 45.0
    assert link.max_travel_time == 60.0
