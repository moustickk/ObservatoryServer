"""Tests des threads dedies (serie, monture) et de l'agent de sauvegarde.

Aucun materiel n'est necessaire : les liaisons sont remplacees par des
doubles qui comptent leurs appels et peuvent echouer a la demande.

Ce que ces tests protegent :
 - un seul thread parle au controleur, jamais deux en meme temps ;
 - un etat qui n'est plus rafraichi devient "perime", donc UNKNOWN ;
 - l'agent de sauvegarde ne ferme jamais sans donnee meteo ni sans monture
   parquee (dans la limite de la grace).
"""

import threading
import time

import pytest

from backend.dome.controller import RoofController
from backend.dome.serial_link import CommandRejected, LinkError
from backend.mount.monitor import MountMonitor
from backend.safety.agent import BackupAgent


# -- doubles -------------------------------------------------------------


class CountingLink:
    """Liaison serie factice : compte les appels simultanes."""

    description = "faux controleur"
    connected = True

    def __init__(self, fail=False):
        self.fail = fail
        self.commands = []
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0

    def send(self, command, timeout=2.0):
        with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)

        try:
            time.sleep(0.01)

            if self.fail:
                raise LinkError("port perdu")

            self.commands.append(command)

            if command == "STATUS":
                return "CLOSED"

            return "OPENING" if command == "OPEN" else "CLOSED"

        finally:
            with self._lock:
                self.in_flight -= 1

    def close(self):
        pass


class RejectingLink(CountingLink):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def send(self, command, timeout=2.0):
        raise self.error


class StubMountLink:
    description = "fausse monture"
    available = True

    def __init__(self, parked=True):
        self.parked = parked
        self.fail = False
        self.calls = 0
        self.park_calls = 0
        self.park_result = True

    def at_park(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("driver absent")
        return self.parked

    def park(self, timeout=None):
        self.park_calls += 1
        if self.park_result:
            self.parked = True
        return self.park_result


# -- thread serie --------------------------------------------------------


def test_un_seul_thread_parle_au_controleur():
    link = CountingLink()
    controller = RoofController(link, poll_seconds=0.01)
    controller.start()

    try:
        def issue(command):
            controller.command(command, timeout=3.0)

        threads = [
            threading.Thread(target=issue, args=(cmd,))
            for cmd in ("OPEN", "CLOSE", "OPEN", "CLOSE", "STOP")
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

    finally:
        controller.close()

    assert link.max_in_flight == 1


def test_le_cache_est_alimente_sans_attendre_une_requete():
    link = CountingLink()
    controller = RoofController(link, poll_seconds=0.01, stale_seconds=1.0)
    controller.start()

    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and controller.snapshot()["stale"]:
            time.sleep(0.02)

        snapshot = controller.snapshot()

    finally:
        controller.close()

    assert snapshot["stale"] is False
    assert snapshot["state"] == "CLOSED"
    assert "STATUS" in link.commands


def test_un_refus_du_controleur_nest_pas_une_panne():
    controller = RoofController(
        RejectingLink(CommandRejected("BUSY", "CLOSING")),
        poll_seconds=0.01,
        stale_seconds=1.0,
    )
    controller.start()

    try:
        with pytest.raises(CommandRejected):
            controller.command("OPEN")

        snapshot = controller.snapshot()

    finally:
        controller.close()

    # Le controleur a repondu : son etat est valide, pas de perte de liaison.
    assert snapshot["state"] == "CLOSING"
    assert snapshot["stale"] is False
    assert snapshot["connected"] is True


def test_une_liaison_morte_finit_par_perimer():
    controller = RoofController(
        CountingLink(fail=True),
        poll_seconds=0.01,
        stale_seconds=0.1,
    )
    controller.start()

    try:
        time.sleep(0.25)
        snapshot = controller.snapshot()

        with pytest.raises(LinkError):
            controller.command("OPEN")

    finally:
        controller.close()

    assert snapshot["stale"] is True
    assert snapshot["connected"] is False
    assert snapshot["last_error"]


def test_une_commande_apres_arret_est_refusee():
    controller = RoofController(CountingLink(), poll_seconds=0.01)
    controller.start()
    controller.stop()

    with pytest.raises(LinkError):
        controller.command("OPEN")


# -- thread monture ------------------------------------------------------


def test_la_monture_est_lue_en_tache():
    link = StubMountLink(parked=True)
    monitor = MountMonitor(link, poll_seconds=0.01, stale_seconds=0.2)
    monitor.start()

    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and monitor.at_park() is None:
            time.sleep(0.02)

        assert monitor.at_park() is True
        assert link.calls >= 1

    finally:
        monitor.stop()


def test_park_met_a_jour_le_cache():
    link = StubMountLink(parked=False)
    monitor = MountMonitor(link, poll_seconds=0.02, stale_seconds=1.0)
    monitor.start()

    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and monitor.at_park() is None:
            time.sleep(0.01)

        assert monitor.at_park() is False

        assert monitor.park(timeout=1) is True

        # Sans rafraichissement immediat, at_park() resterait None jusqu'au
        # prochain sondage et le toit serait refuse entre-temps.
        assert monitor.at_park() is True

    finally:
        monitor.stop()


def test_une_monture_injoignable_devient_indeterminee():
    link = StubMountLink(parked=True)
    monitor = MountMonitor(link, poll_seconds=0.01, stale_seconds=0.1)
    monitor.start()

    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and monitor.at_park() is None:
            time.sleep(0.02)

        link.fail = True
        time.sleep(0.3)

        assert monitor.at_park() is None
        assert monitor.last_error

    finally:
        monitor.stop()


# -- agent de sauvegarde -------------------------------------------------


class StubSafety:
    def __init__(self, safe, age=1):
        self._status = {"safe": safe, "data_age_minutes": age}

    def status(self):
        return self._status


class StubState:
    def __init__(self, state):
        self.data = {"state": state}
        self.alarm = None

    def get(self, key, default=None):
        return self.data.get(key, default)

    def raise_alarm(self, code, message):
        self.alarm = {"code": code, "message": message}


class StubDome:
    mount_check_mode = "strict"

    def __init__(self, state="OPENED", parked=True):
        self.state = StubState(state)
        self.mount = StubMountLink(parked)
        self.closed = 0
        self.stopped = 0

    def close(self):
        self.closed += 1
        self.state.data["state"] = "CLOSING"
        return {"ok": True, "state": "CLOSING"}

    def stop(self):
        self.stopped += 1
        return {"ok": True, "state": "STOPPED"}


def make_agent(dome, safety, grace=0.1, enabled=True, auto_park=False):
    return BackupAgent(
        dome,
        safety,
        {
            "park_grace_seconds": grace,
            "safety_agent_enabled": enabled,
            "auto_park_mount": auto_park,
            "park_timeout": 1,
        },
        grace_poll_seconds=0.01,
    )


def test_agent_ferme_quand_la_meteo_est_dangereuse():
    dome = StubDome(state="OPENED", parked=True)
    agent = make_agent(dome, StubSafety(safe=False))

    assert agent.tick() == "closed"
    assert dome.closed == 1


def test_agent_ne_ferme_pas_sans_donnee_meteo():
    """Au demarrage, is_safe vaut False mais aucune mesure n'existe."""

    dome = StubDome(state="OPENED")
    agent = make_agent(dome, StubSafety(safe=False, age=-1))

    assert agent.tick() == "no_data"
    assert dome.closed == 0


def test_agent_ne_ferme_pas_une_monture_non_parquee():
    dome = StubDome(state="OPENED", parked=False)
    agent = make_agent(dome, StubSafety(safe=False), grace=0.05)

    assert agent.tick() == "not_parked"
    assert dome.closed == 0
    assert dome.state.alarm["code"] == "ROOF_UNSAFE_NOT_PARKED"


def test_agent_attend_que_la_monture_se_parque():
    dome = StubDome(state="OPENED", parked=False)
    agent = make_agent(dome, StubSafety(safe=False), grace=1.0)

    # La monture se parque pendant l'attente.
    threading.Timer(0.05, lambda: setattr(dome.mount, "parked", True)).start()

    assert agent.tick() == "closed"
    assert dome.closed == 1


def test_agent_ne_fait_rien_quand_la_meteo_est_sure():
    dome = StubDome(state="OPENED")
    agent = make_agent(dome, StubSafety(safe=True))

    assert agent.tick() == "safe"
    assert dome.closed == 0


def test_agent_interrompt_une_ouverture_avant_de_fermer():
    dome = StubDome(state="OPENING", parked=True)
    agent = make_agent(dome, StubSafety(safe=False))

    assert agent.tick() == "closed"
    assert dome.stopped == 1
    assert dome.closed == 1


def test_agent_ne_ferme_pas_deux_fois():
    dome = StubDome(state="OPENED", parked=True)
    agent = make_agent(dome, StubSafety(safe=False))

    agent.tick()
    assert agent.tick() == "already"
    assert dome.closed == 1


def test_agent_referme_sans_delai_apres_une_reouverture():
    """Le delai de repos ne doit s'appliquer qu'aux echecs."""

    dome = StubDome(state="OPENED", parked=True)
    agent = make_agent(dome, StubSafety(safe=False))

    assert agent.tick() == "closed"
    assert dome.closed == 1

    # Le toit est rouvert aussitot, meteo toujours dangereuse.
    dome.state.data["state"] = "OPENED"

    assert agent.tick() == "closed"
    assert dome.closed == 2


def test_agent_ne_reattente_pas_immediatement():
    dome = StubDome(state="OPENED", parked=False)
    agent = make_agent(dome, StubSafety(safe=False), grace=0.02)

    assert agent.tick() == "not_parked"
    assert agent.tick() == "backoff"


def test_agent_ne_fait_rien_pendant_la_maintenance():
    """Televersement Arduino : la liaison est suspendue, l'agent se tait."""

    dome = StubDome(state="CLOSED", parked=True)
    dome.maintenance = True

    agent = make_agent(dome, StubSafety(safe=False))

    assert agent.tick() == "maintenance"
    assert dome.closed == 0


def test_agent_desactive_ne_ferme_rien():
    """Essai supervise : l'agent doit rester muet, meme sous la pluie."""

    dome = StubDome(state="OPENED", parked=True)
    agent = make_agent(dome, StubSafety(safe=False), enabled=False)

    assert agent.tick() == "disabled"
    assert agent.start() is None
    assert dome.closed == 0


def test_agent_parque_la_monture_quand_cest_autorise():
    """Sans personne pour parquer, l'agent le fait avant de fermer."""

    dome = StubDome(state="OPENED", parked=False)
    agent = make_agent(dome, StubSafety(safe=False), auto_park=True, grace=0.05)

    assert agent.tick() == "closed"
    assert dome.mount.park_calls == 1
    assert dome.closed == 1


def test_agent_ne_parque_pas_par_defaut():
    dome = StubDome(state="OPENED", parked=False)
    agent = make_agent(dome, StubSafety(safe=False), grace=0.02)

    assert agent.tick() == "not_parked"
    assert dome.mount.park_calls == 0
    assert dome.closed == 0


def test_agent_alarme_si_le_parkage_echoue():
    dome = StubDome(state="OPENED", parked=False)
    dome.mount.park_result = False
    agent = make_agent(dome, StubSafety(safe=False), auto_park=True, grace=0.02)

    assert agent.tick() == "not_parked"
    assert dome.mount.park_calls == 1
    assert dome.closed == 0
    assert dome.state.alarm["code"] == "ROOF_UNSAFE_NOT_PARKED"


# -- parkage a la demande ------------------------------------------------


class SilentRoof:
    description = "faux controleur"

    def snapshot(self):
        return {
            "state": "CLOSED",
            "stale": False,
            "connected": True,
            "description": self.description,
            "last_error": None,
            "age": 0.0,
        }

    def command(self, name, timeout=5.0):
        return "CLOSED"


def test_park_mount_repond_sans_bloquer(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.common.state.STATE_FILE",
        tmp_path / "roof_state.json",
    )

    from backend.dome.service import DomeService

    mount = StubMountLink(parked=False)
    dome = DomeService(SilentRoof(), mount, {"full_travel_time": 48})

    started = time.monotonic()
    result = dome.park_mount(timeout=1)
    elapsed = time.monotonic() - started

    assert result["ok"] is True
    # Le parkage part en tache de fond : l'appelant n'attend pas le driver.
    assert elapsed < 0.5

    deadline = time.monotonic() + 2.0
    while mount.park_calls == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert mount.park_calls == 1
