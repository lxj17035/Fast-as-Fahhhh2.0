"""Reserve and send the exact saved PDF through Xinjie's real service methods."""

import base64
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.engine import Connection

from app.quotation_contract import (
    QuotationConflict,
    QuotationItem,
    QuotationNotFound,
    QuotationNotReady,
    SavedQuotation,
)
from app.xinjie_store import Store
from backend.errors import AppError
from backend.quotations import QuotationService
from backend.settings import SettingsService
from backend.review import telegram_summary


def translate_error(error: AppError):
    if error.status == 404:
        return QuotationNotFound()
    if error.status == 409:
        return QuotationConflict()
    return QuotationNotReady()


class XinjieQuotationProvider:
    def reserve_for_send(
        self, connection: Connection, quotation_id: str, expected_version: int
    ) -> SavedQuotation:
        store = Store(connection.engine, connection)
        key = UUID(quotation_id).hex
        try:
            with store.transaction():
                service = QuotationService(store, SettingsService(store))
                quote = service.validate_for_send(key, expected_version, "pm")
                try:
                    cached = store.get("pdfs", f"{key}:{expected_version}")
                except AppError as error:
                    if error.status == 404:
                        raise QuotationConflict("Saved preview is required") from None
                    raise
                pdf = base64.b64decode(cached["data"], validate=True)
                result = SavedQuotation(
                    quotation_id=str(UUID(key)),
                    enquiry_id=str(UUID(quote["enquiryId"])),
                    version=quote["version"],
                    status="draft",
                    client_name=quote["client"]["name"],
                    issue_date=date.fromisoformat(quote["issueDate"]),
                    expiry_date=date.fromisoformat(quote["expiryDate"]),
                    items=tuple(
                        QuotationItem(
                            description=item["description"],
                            quantity=Decimal(item["quantity"]),
                            unit_price=Decimal(item["unitPrice"]),
                        )
                        for item in quote["items"]
                    ),
                    pdf_version=quote["version"],
                    pdf_bytes=pdf,
                    telegram_summary=telegram_summary(quote),
                    source_message_ids=tuple(service.source_ids(quote["enquiryId"])),
                )
                service.begin_send(key, expected_version, "pm", "pm")
                return result
        except AppError as error:
            raise translate_error(error) from None

    def record_outcome(
        self, connection: Connection, quotation_id: str, status: str,
        provider_reference: str | None = None,
    ) -> None:
        store = Store(connection.engine, connection)
        try:
            with store.transaction():
                service = QuotationService(store, SettingsService(store))
                service.record_send_result(
                    UUID(quotation_id).hex,
                    {"sent": "accepted", "failed": "failed", "unknown": "uncertain"}[
                        status
                    ],
                    provider_reference=provider_reference,
                )
        except AppError as error:
            raise translate_error(error) from None
