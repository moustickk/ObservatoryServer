"""Codes d'erreur ASCOM Alpaca.

Les valeurs sont celles de la specification Alpaca (troncature des HResult
COM). Elles sont volontairement ecrites en decimal : c'est ce que NINA lit
dans le champ `ErrorNumber`.
"""

# Succes.
SUCCESS = 0

# Propriete ou methode non implementee (0x400).
NOT_IMPLEMENTED = 1024

# Valeur invalide (0x401).
INVALID_VALUE = 1025

# Valeur non definie (0x402).
VALUE_NOT_SET = 1026

# Device non connecte (0x407).
NOT_CONNECTED = 1031

# Operation interdite dans l'etat courant (0x40B).
INVALID_OPERATION = 1035

# Action non implementee (0x40C).
ACTION_NOT_IMPLEMENTED = 1036

# Erreur non specifiee, categorie client (0x4FF).
UNSPECIFIED = 1279

# Erreur du pilote / du serveur (0x500).
DRIVER_ERROR = 1280


class AlpacaError(Exception):
    """Erreur renvoyee au client dans l'enveloppe Alpaca."""

    def __init__(self, number, message):
        super().__init__(message)
        self.number = int(number)
        self.message = str(message)

    @property
    def http_status(self):
        """400 pour une erreur client, 500 pour une erreur device."""

        if (self.number & 0xF00) == 0x500:
            return 500
        return 400

    def __str__(self):
        return self.message
