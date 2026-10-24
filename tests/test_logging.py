"""Tests de la journalisation applicative (phase 6).

Ce que ces tests protegent :
 - ecrire ne relit plus le fichier : une ligne etrangere reste en place ;
 - plusieurs threads peuvent journaliser sans se perdre de lignes ;
 - la purge retire les entrees de plus de 48 h sans toucher aux recentes ;
 - un message multiligne ne casse pas le format une-ligne-par-entree.
"""

import threading
from datetime import datetime, timedelta

from backend.common import logger


def read_log(path):
    return path.read_text(encoding="utf-8")


def test_ecriture_en_ajout_sans_reecriture(tmp_path, monkeypatch):
    """L'ancien code relisait et reecrivait tout : cette ligne disparaissait."""

    monkeypatch.setattr(logger, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger, "_last_purge", {})

    log_file = tmp_path / "roof.log"
    log_file.write_text("ligne ajoutee a la main, sans horodatage\n", encoding="utf-8")

    logger.write_log("roof.log", "premier")
    logger.write_log("roof.log", "second")

    content = read_log(log_file)

    assert "ligne ajoutee a la main" in content
    assert content.count("premier") == 1
    assert content.count("second") == 1
    # L'ordre d'arrivee est conserve.
    assert content.index("premier") < content.index("second")


def test_plusieurs_threads_ne_perdent_aucune_ligne(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger, "_last_purge", {})

    total = 25
    workers = 8

    def writer(index):
        for count in range(total):
            logger.write_log("roof.log", f"thread {index} ligne {count}")

    threads = [
        threading.Thread(target=writer, args=(index,))
        for index in range(workers)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    lines = [
        line
        for line in read_log(tmp_path / "roof.log").splitlines()
        if line.strip()
    ]

    assert len(lines) == total * workers


def test_la_purge_retire_seulement_les_lignes_anciennes(tmp_path):
    log_file = tmp_path / "meteo_log.txt"

    old = (datetime.now() - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
    recent = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    log_file.write_text(
        f"[{old}] vieille mesure\n"
        f"ligne sans horodatage\n"
        f"[{recent}] mesure recente\n",
        encoding="utf-8",
    )

    kept = logger._purge(log_file, retention_seconds=48 * 3600)

    content = read_log(log_file)

    assert kept == 2
    assert "vieille mesure" not in content
    assert "ligne sans horodatage" in content
    assert "mesure recente" in content


def test_un_message_multiligne_reste_sur_une_ligne(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger, "_last_purge", {})

    logger.write_log("roof.log", "erreur\nsur deux lignes")

    lines = read_log(tmp_path / "roof.log").splitlines()

    assert len(lines) == 1
    assert "erreur | sur deux lignes" in lines[0]


def test_le_format_commence_par_un_horodatage(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger, "_last_purge", {})

    logger.write_log("roof.log", "OPEN command")

    line = read_log(tmp_path / "roof.log").splitlines()[0]

    assert line.startswith("[")
    assert line[21:] == " OPEN command"
    datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
