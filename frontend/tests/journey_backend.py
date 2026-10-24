"""Empty, disposable actual API for Phase 4 UI journeys; never reads .env."""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import os
import sys

from sqlalchemy import create_engine
import uvicorn

from app.config import Settings
from app.main import create_app
from backend.drafting import DisabledExtractor
from tests.phase4_support import ScenarioTelegram, scenario_extractor


def main():
    scratch = Path(__file__).resolve().parents[2] / '.input'
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='phase4-ui-', dir=scratch) as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'qa.db'}",
                               connect_args={'check_same_thread': False})
        sender = ScenarioTelegram()
        application = create_app(Settings(database_url='synthetic-injected-engine',
            telegram_webhook_secret='synthetic-phase4-secret', enable_demo_approval=True),
            engine, telegram_sender=sender, ai_extractor=DisabledExtractor())
        original_lifespan = application.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app):
            async with original_lifespan(app):
                service = app.state.quotation_app
                service.drafts.extractor = scenario_extractor(service.store, [])
                yield

        application.router.lifespan_context = lifespan
        server = uvicorn.Server(uvicorn.Config(application, host='127.0.0.1',
            port=int(os.environ['FRONTEND_QA_PORT']), access_log=False))

        def stop():
            if sys.stdin.readline().strip() == 'stop':
                server.should_exit = True

        Thread(target=stop, daemon=True).start()
        try:
            server.run()
        finally:
            engine.dispose()


if __name__ == '__main__':
    main()
