"""Run with: uvicorn app.main:create_app --factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.database import metadata
from app.telegram import router


def create_app(
    settings: Settings | None = None, engine: Engine | None = None
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
            except SQLAlchemyError:
                raise RuntimeError("Database initialization failed") from None
            yield
        finally:
            if owns_engine:
                await run_in_threadpool(engine.dispose)

    application = FastAPI(title="Sweeway", lifespan=lifespan)
    application.state.settings = settings
    application.state.engine = engine
    application.include_router(router)
    return application
