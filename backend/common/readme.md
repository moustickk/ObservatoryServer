Common Module

Responsabilités :

- Configuration globale (settings_manager : validation, types, écriture atomique)
- Accès aux réglages (config.py)
- Journalisation
- État persistant (écriture atomique)
- Gestion des chemins
- Version de l'application
- Vue de santé agrégée (health.py)

Note : le registre de services, le bootstrap et l'initialisation globale ont été
supprimés. C'est le conteneur (backend/container.py) qui construit les services
au démarrage de l'application, jamais à l'import.
