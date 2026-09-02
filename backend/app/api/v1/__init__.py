from fastapi import APIRouter

from app.api.v1 import alerts, auth, health, market, portfolio, telegram

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(market.router)
api_router.include_router(portfolio.router)
api_router.include_router(alerts.router)
api_router.include_router(telegram.router)
api_router.include_router(health.router)

__all__ = ["api_router"]
