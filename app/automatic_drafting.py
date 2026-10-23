"""Start drafting after durable receipt; failures never discard the enquiry."""
import logging
from threading import Lock

from sqlalchemy import select

from app.database import enquiries

logger = logging.getLogger(__name__)


class AutomaticDrafting:
    def __init__(self, engine, quotation_app):
        self.engine = engine
        self.app = quotation_app
        self.lock = Lock()
        self.active = set()

    def run(self, update_id):
        with self.lock:
            if update_id in self.active:
                return
            self.active.add(update_id)
        try:
            with self.engine.connect() as connection:
                enquiry_id = connection.execute(select(enquiries.c.id).where(
                    enquiries.c.telegram_update_id == update_id)).scalar_one()
            self.app.drafts.create(enquiry_id)
        except Exception:
            # No raw exception/provider text: it may contain connection secrets.
            # Receipt is already committed, so staff can retry the draft endpoint.
            logger.warning("Automatic draft did not complete; the enquiry remains available for review/retry")
        finally:
            with self.lock:
                self.active.discard(update_id)
