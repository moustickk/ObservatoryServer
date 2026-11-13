"""Tests de coexistence serveur / NINA sur EQMOD.

Le serveur ne doit jamais creer une seconde instance EQMOD quand NINA tourne :
EQMOD ne sait pas forcement en gerer deux, et la creation en boucle a deja
fait perdre la monture a NINA.
"""

import time

import pytest

from backend.mount import link


pytestmark = pytest.mark.skipif(
    not link.ASCOM_AVAILABLE,
    reason="ASCOM/pywin32 indisponible",
)


class FauxScope:
    def __init__(self, connected=True, at_park=True):
        self.Connected = connected
        self.AtPark = at_park


class FauxClient:
    def __init__(self, active_error=False, dispatch_scope=None, active_scope=None):
        self.active_error = active_error
        self.dispatch_scope = dispatch_scope or FauxScope()
        self.active_scope = active_scope
        self.get_active_calls = 0
        self.dispatch_calls = 0
        self.dispatch_ex_calls = 0

    def GetActiveObject(self, prog_id):
        self.get_active_calls += 1
        if self.active_error:
            raise RuntimeError("absent du ROT")
        return self.active_scope

    def Dispatch(self, prog_id):
        self.dispatch_calls += 1
        return self.dispatch_scope

    def DispatchEx(self, prog_id):
        self.dispatch_ex_calls += 1
        return self.dispatch_scope


class FauxWin32:
    def __init__(self, client):
        self.client = client


@pytest.fixture(autouse=True)
def reset_cache():
    link._nina_cache["at"] = 0.0
    link._nina_cache["running"] = False
    yield
    link._nina_cache["at"] = 0.0
    link._nina_cache["running"] = False


def make_link(monkeypatch, client, nina=False, nina_autostart=False):
    monkeypatch.setattr(link, "nina_running", lambda: nina)
    monkeypatch.setattr(link, "win32com", FauxWin32(client))
    return link.AscomMountLink(
        "EQMOD.Telescope",
        nina_autostart=nina_autostart,
    )


def test_pas_de_nouvelle_instance_si_nina_tourne(monkeypatch):
    client = FauxClient(active_error=True)

    mount = make_link(monkeypatch, client, nina=True)

    assert mount.at_park() is None
    assert client.dispatch_calls == 0
    assert "NINA" in mount.last_error


def test_utilise_l_instance_de_nina_si_elle_existe(monkeypatch):
    client = FauxClient(active_scope=FauxScope(connected=True, at_park=True))

    mount = make_link(monkeypatch, client, nina=True)

    assert mount.at_park() is True
    assert client.dispatch_calls == 0


def test_une_instance_nina_deconnectee_est_signalee(monkeypatch):
    client = FauxClient(active_scope=FauxScope(connected=False, at_park=True))

    mount = make_link(monkeypatch, client, nina=True)

    assert mount.at_park() is None
    assert "deconnectee" in mount.last_error
    assert client.dispatch_calls == 0


def test_nouvelle_instance_autorisee_sans_nina(monkeypatch):
    client = FauxClient(active_error=True, dispatch_scope=FauxScope(True, True))

    mount = make_link(monkeypatch, client, nina=False)

    assert mount.at_park() is True
    assert client.dispatch_calls == 1


def test_instance_orpheline_est_remplacee_sans_nina(monkeypatch):
    client = FauxClient(
        active_scope=FauxScope(connected=False),
        dispatch_scope=FauxScope(True, True),
    )

    mount = make_link(monkeypatch, client, nina=False)

    assert mount.at_park() is True
    assert client.dispatch_calls == 1


def test_backoff_apres_echec(monkeypatch):
    client = FauxClient(active_error=True)

    mount = make_link(monkeypatch, client, nina=True)

    assert mount.at_park() is None
    assert mount.at_park() is None

    # La deuxieme lecture doit utiliser le backoff, sans nouvel appel COM.
    assert client.get_active_calls == 1


def test_reconnexion_refusee_si_nina_tourne(monkeypatch):
    client = FauxClient()
    mount = make_link(monkeypatch, client, nina=True)

    monkeypatch.setattr(
        link.driver,
        "restart",
        lambda prog_id: (_ for _ in ()).throw(AssertionError("ne doit pas tuer EQMOD")),
    )

    assert mount.reconnect() is False
    assert client.dispatch_ex_calls == 0


def test_attente_du_demarrage_de_nina(monkeypatch):
    client = FauxClient(active_error=True)

    mount = make_link(monkeypatch, client, nina=False, nina_autostart=True)

    assert mount.at_park() is None
    assert "attente du demarrage de NINA" in mount.last_error
    assert client.dispatch_calls == 0

    # Apres le delai de grace, le serveur peut reprendre la main.
    mount._created_at -= link.NINA_START_GRACE_SECONDS + 1
    mount._next_probe = 0.0

    assert mount.at_park() is True
    assert client.dispatch_calls == 1
