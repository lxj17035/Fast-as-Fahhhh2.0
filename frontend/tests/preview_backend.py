"""Actual FastAPI app with temporary SQLite and synthetic, mocked providers.

QA only: python -m frontend.tests.preview_backend
Never loads .env, uses PostgreSQL runtime data, or contacts Telegram/AI.
Close with Ctrl+C to remove the temporary database.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
import uvicorn

from app.config import Settings
from app.database import save_update
from app.main import create_app
from app.telegram_client import DeliveryResult


class SyntheticExtractor:
    def extract(self, message, context):
        return {
            "summary": "Fictional event team requests 20 printed cotton T-shirts for their next event.",
            "clientName": "Example Events (fictional)",
            "clientAddress": "12 Demo Road, Fictional Town",
            "items": [{"description": "Cotton event T-shirts with front print", "quantity": "20", "unitPrice": None}],
            "missingInformation": ["Confirm print colour with the client"],
        }


class SyntheticSender:
    def __init__(self):
        self.calls = 0

    def send_pdf(self, chat_id, pdf):
        self.calls += 1
        print("MOCKED Telegram attempt:", self.calls, "PDF bytes:", len(pdf))
        if self.calls == 1:
            return DeliveryResult("failed", error_code="telegram_403")
        if self.calls == 3:
            return DeliveryResult("unknown", error_code="telegram_timeout")
        return DeliveryResult("sent", message_id=str(42000 + self.calls))


def main():
    with TemporaryDirectory(prefix="quoteflow_frontend_qa_") as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'qa.db'}", connect_args={"check_same_thread": False})
        settings = Settings(database_url="synthetic-injected-test-engine", telegram_webhook_secret="synthetic-qa-secret", enable_demo_approval=True)
        app = create_app(settings, engine, ai_extractor=SyntheticExtractor(), telegram_sender=SyntheticSender())
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            async with original_lifespan(application):
                for index, message in enumerate([
                    "Example Events needs 20 printed cotton T-shirts. Address: 12 Demo Road. Please share a quotation.",
                    "Fictional Workshop: quotation for 20 staff uniforms with our front logo.",
                    "Demo Market requests printed tote bags for a community event. Quantity to be confirmed.",
                    "Example Studio: please quote for event crew shirts. <script>alert('test')</script>",
                ]):
                    save_update(engine, 9000 + index, 100 + index, -1001234567890, message)
                    application.state.automatic_drafting.run(9000 + index)
                print("QA ONLY: actual backend, temporary SQLite, mocked AI and Telegram.")
                print("First send fails, second succeeds, third is unknown. No external calls.")
                yield

        app.router.lifespan_context = lifespan
        try:
            uvicorn.run(app, host="127.0.0.1", port=8004, access_log=False)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
