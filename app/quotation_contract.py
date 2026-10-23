"""Integration boundary for saved quotations and exact previewed PDFs."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine import Connection


class IntegrationUnavailable(Exception):
    """The saved quotation/PDF service has not been connected."""


class QuotationConflict(Exception):
    """The saved quotation is stale, reserved, or no longer sendable."""


class QuotationNotFound(Exception):
    """The requested saved quotation does not exist."""


class QuotationNotReady(Exception):
    """Saved quotation has unresolved required fields."""


class QuotationItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    description: str
    quantity: Decimal
    unit_price: Decimal | None


class SavedQuotation(BaseModel):
    model_config = ConfigDict(frozen=True)
    quotation_id: str
    enquiry_id: str
    version: Annotated[int, Field(strict=True, gt=0)]
    status: Literal["draft", "ready"]
    client_name: str
    issue_date: date
    expiry_date: date
    items: tuple[QuotationItem, ...]
    pdf_version: Annotated[int, Field(strict=True, gt=0)]
    pdf_bytes: bytes


class QuotationProvider(Protocol):
    def reserve_for_send(
        self, connection: Connection, quotation_id: str, expected_version: int
    ) -> SavedQuotation:
        """Lock, validate current state/version, and reserve within this transaction.

        All quotation edits must honor the persisted reservation. The returned
        bytes must be the saved PDF of that exact version, never a new rendering.
        """
        ...

    def record_outcome(
        self, connection: Connection, quotation_id: str, status: str,
        provider_reference: str | None = None,
    ) -> None:
        """Persist the outcome using the same transaction as the delivery record."""
        ...


class UnavailableQuotationProvider:
    def reserve_for_send(
        self, connection: Connection, quotation_id: str, expected_version: int
    ) -> SavedQuotation:
        raise IntegrationUnavailable()

    def record_outcome(
        self, connection: Connection, quotation_id: str, status: str,
        provider_reference: str | None = None,
    ) -> None:
        raise IntegrationUnavailable()
