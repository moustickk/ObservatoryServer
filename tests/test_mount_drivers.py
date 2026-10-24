"""Tests de la decouverte des pilotes ASCOM (selecteur de l'interface)."""

import os

from backend.mount import drivers


def test_liste_des_pilotes_a_la_bonne_forme():
    found = drivers.list_drivers()

    assert isinstance(found, list)

    if os.name != "nt":
        assert found == []
        return

    for item in found:
        assert item["prog_id"]
        assert item["name"]

    identifiers = [item["prog_id"] for item in found]
    assert len(identifiers) == len(set(identifiers))


def test_les_pilotes_sont_tries_par_nom():
    names = [item["name"].lower() for item in drivers.list_drivers()]

    assert names == sorted(names)
