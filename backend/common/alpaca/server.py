"""Routeur Alpaca agrege.

`backend.app` n'inclut que ce routeur : management, Dome et SafetyMonitor
partagent le meme port HTTP que l'API REST de l'observatoire.
"""

from fastapi import APIRouter

from backend.common.alpaca import dome, management, safetymonitor


router = APIRouter()
router.include_router(management.router)
router.include_router(dome.router)
router.include_router(safetymonitor.router)
