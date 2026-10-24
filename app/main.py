"""Run with: uvicorn app.main:create_app --factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.migrations import upgrade_business_profile_schema, upgrade_delivery_schema
from backend.config import load_env
from backend.errors import AppError
from backend.store import Store as BootstrapStore
from backend.server import Application, ALLOWED_ORIGINS
from app.xinjie_store import Store
from app.quotations import router as supplemental_router
from app.automatic_drafting import AutomaticDrafting
from app.database import backfill_enquiries, metadata
from app.delivery import router as delivery_router
from app.enquiries import router as enquiries_router
from app.telegram import router
from app.routing import router as assignment_router
from app.conversations import router as conversation_router
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
    if settings is None:
        load_env(Path(__file__).resolve().parent.parent / ".env")
        settings = Settings.from_env()
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
                await run_in_threadpool(upgrade_business_profile_schema, engine)
                await run_in_threadpool(upgrade_delivery_schema, engine)
                await run_in_threadpool(backfill_enquiries, engine)
                await run_in_threadpool(lambda: BootstrapStore(engine=engine))
                store = Store(engine)
                application.state.quotation_app = await run_in_threadpool(
                    lambda: Application(store, extractor=ai_extractor, telegram_token=settings.telegram_bot_token))
                application.state.automatic_drafting = AutomaticDrafting(engine, application.state.quotation_app)
            except SQLAlchemyError:
                raise RuntimeError("Database initialization failed") from None
            yield
        finally:
            if owns_engine:
                await run_in_threadpool(engine.dispose)

    application = FastAPI(title="QuoteFlow (working title)", lifespan=lifespan)
    application.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS),
                               allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
                               allow_headers=["Content-Type", "X-Demo-Actor"], expose_headers=["X-Quotation-Version"])

    @application.exception_handler(AppError)
    async def quotation_error(request, error):
        return JSONResponse({"error": str(error), "fields": error.fields}, status_code=error.status)

    @application.exception_handler(SQLAlchemyError)
    async def storage_error(request, error):
        return JSONResponse({"error": "Storage unavailable; no successful action is implied", "fields": {}}, status_code=503)
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
    application.include_router(assignment_router)
    application.include_router(conversation_router)
    application.include_router(enquiries_router)
    application.include_router(delivery_router)
    application.include_router(quotation_router)
    application.include_router(supplemental_router)
    return application
