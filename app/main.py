"""Run with: uvicorn app.main:create_app --factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.database import backfill_enquiries, metadata
from app.delivery import router as delivery_router
from app.enquiries import router as enquiries_router
from app.telegram import router
from app.quotation_contract import QuotationProvider
from app.telegram_client import TelegramSender
from app.xinjie_adapter import XinjieQuotationProvider
from app.quotation_routes import router as quotation_router


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    quotation_provider: QuotationProvider | None = None,
    telegram_sender: TelegramSender | None = None,
    ai_extractor: object | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env()
    owns_engine = engine is None
    engine = (
        engine
        if engine is not None
        else create_engine(settings.database_url, pool_pre_ping=True)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            # Prototype bootstrap only; schema evolution will need migrations.
            try:
                await run_in_threadpool(metadata.create_all, engine)
                await run_in_threadpool(backfill_enquiries, engine)
            except SQLAlchemyError:
                raise RuntimeError("Database initialization failed") from None
            yield
        finally:
            if owns_engine:
                await run_in_threadpool(engine.dispose)

    application = FastAPI(title="Sweeway", lifespan=lifespan)
    application.state.settings = settings
    application.state.engine = engine
    application.state.ai_extractor = ai_extractor
    application.state.quotation_provider = (
        quotation_provider
        if quotation_provider is not None
        else XinjieQuotationProvider()
    )
    application.state.telegram_sender = (
        telegram_sender
        if telegram_sender is not None
        else TelegramSender(settings.telegram_bot_token)
        if settings.telegram_bot_token
        else None
    )
    application.include_router(router)
    application.include_router(enquiries_router)
    application.include_router(delivery_router)
    application.include_router(quotation_router)
    return application
