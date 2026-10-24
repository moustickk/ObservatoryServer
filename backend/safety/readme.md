Safety Module

Responsabilités :

- Récupération météo
- Analyse météo
- Cache météo
- Logs météo
- Etat SAFE / UNSAFE
- DeviceState Alpaca

Fichiers :

config.py              Paramètres du module
weather_provider.py    Récupération Open-Meteo
parser.py              Conversion des données météo
models.py              Modèles de données
evaluator.py           Evaluation des seuils
engine.py              Traitement météo
monitor.py             Boucle de surveillance
status.py              Etat interne
device_state.py        Données Alpaca
logging.py             Journalisation
state.py               Etat global