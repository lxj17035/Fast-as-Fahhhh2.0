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
from backend.config import load_env
from backend.errors import AppError
from backend.server import Application, ALLOWED_ORIGINS
from backend.store import Store
from app.quotations import router as quotation_router
from app.automatic_drafting import AutomaticDrafting
from app.database import backfill_enquiries, metadata
from app.enquiries import router as enquiries_router
from app.telegram import router


def create_app(
    settings: Settings | None = None, engine: Engine | None = None
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
                await run_in_threadpool(backfill_enquiries, engine)
                store = await run_in_threadpool(lambda: Store(engine=engine))
                application.state.quotation_app = await run_in_threadpool(lambda: Application(store))
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
                               allow_headers=["Content-Type"], expose_headers=["X-Quotation-Version"])

    @application.exception_handler(AppError)
    async def quotation_error(request, error):
        return JSONResponse({"error": str(error), "fields": error.fields}, status_code=error.status)
    application.state.settings = settings
    application.state.engine = engine
    application.include_router(router)
    application.include_router(enquiries_router)
    application.include_router(quotation_router)
    return application
