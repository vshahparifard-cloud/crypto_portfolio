"""FastAPI application factory."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v1.health import config_warnings
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.services.cache import close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)


log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    for warning in config_warnings():
        log.warning("configuration: %s", warning)
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CoinPulse API",
        version="0.1.0",
        description=(
            "سبد ارز دیجیتال با هشدار قیمتی و اطلاع‌رسانی تلگرام. "
            "قیمت‌ها هر ۵ دقیقه از CoinGecko نمونه‌گیری می‌شوند."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
