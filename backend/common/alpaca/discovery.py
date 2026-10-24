"""Decouverte Alpaca (UDP 32227).

Un client diffuse `alpacadiscovery1` sur le port 32227 ; chaque serveur
repond en unicast `{"AlpacaPort": n}`. C'est ainsi que NINA trouve le dome et
le Safety Monitor sans saisie manuelle de port.

Le socket est cree dans un thread dedie. Si le port est deja occupe (autre
serveur Alpaca, ASCOM Remote), on journalise l'erreur sans empecher le
demarrage : la saisie manuelle du port reste possible.
"""

import json
import logging
import socket
import threading


log = logging.getLogger(__name__)

DISCOVERY_PORT = 32227
DISCOVERY_MESSAGE = b"alpacadiscovery"
RECV_BUFFER = 1024


class DiscoveryResponder:
    """Repond aux diffusions de decouverte Alpaca."""

    def __init__(self, alpaca_port, port=DISCOVERY_PORT):
        self.alpaca_port = int(alpaca_port)
        self.port = int(port)
        self._stop = threading.Event()
        self._thread = None
        self._socket = None

    # -- cycle de vie ----------------------------------------------------

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="alpaca-discovery",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

        sock = self._socket
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    # -- boucle ----------------------------------------------------------

    def _open_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Autorise plusieurs serveurs Alpaca sur la meme machine.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        sock.settimeout(1.0)
        sock.bind(("", self.port))
        return sock

    def _run(self):
        try:
            self._socket = self._open_socket()
        except OSError as ex:
            log.error(
                "Decouverte Alpaca indisponible (UDP %s) : %s. "
                "Utiliser la saisie manuelle du port dans NINA.",
                self.port,
                ex,
            )
            return

        log.info("Decouverte Alpaca a l'ecoute sur UDP %s", self.port)

        payload = json.dumps({"AlpacaPort": self.alpaca_port}).encode("utf-8")

        try:
            while not self._stop.is_set():
                try:
                    data, address = self._socket.recvfrom(RECV_BUFFER)
                except socket.timeout:
                    continue
                except OSError:
                    break

                message = (data or b"").strip().lower()

                if not message.startswith(DISCOVERY_MESSAGE):
                    continue

                try:
                    self._socket.sendto(payload, address)
                except OSError as ex:
                    log.debug("Reponse de decouverte non envoyee a %s : %s", address, ex)
                else:
                    log.debug("Decouverte repondue a %s", address)
        finally:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
            log.info("Decouverte Alpaca arretee")
