"""Controlled demo delivery of the saved quotation version approved by PM."""

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Annotated, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import enquiries, send_attempts, telegram_updates
from app.quotation_contract import (
    IntegrationUnavailable,
    QuotationConflict,
    QuotationNotFound,
    QuotationNotReady,
    SavedQuotation,
)
from app.telegram_client import DeliveryResult
from app.xinjie_store import integration_transaction

router = APIRouter(prefix="/api/quotations", tags=["delivery"])
MAX_PDF_BYTES = 10 * 1024 * 1024


def safe_error_code(value: str | None) -> str | None:
    if value is None or value in {
        "invalid_response", "telegram_timeout", "telegram_transport_error",
        "unconfirmed_response", "unexpected_send_error",
    }:
        return value
    if re.fullmatch(r"telegram_4[0-9]{2}", value):
        return value
    return "unclassified_delivery_error"


class SendApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]
    approved: Literal[True]

    @field_validator("approved", mode="before")
    @classmethod
    def explicit_approval(cls, value: object) -> object:
        if value is not True:
            raise ValueError("Explicit approval is required")
        return value


def validate_quotation(
    quotation: SavedQuotation, quotation_id: str, expected_version: int
) -> None:
    if (
        quotation.quotation_id != quotation_id
        or quotation.version != expected_version
        or quotation.pdf_version != expected_version
        or quotation.status not in {"draft", "ready"}
    ):
        raise HTTPException(status_code=409, detail="Quotation version unavailable")
    today = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date()
    valid = (
        bool(quotation.client_name.strip())
        and bool(quotation.items)
        and quotation.issue_date <= today <= quotation.expiry_date
        and quotation.issue_date <= quotation.expiry_date
        and quotation.pdf_bytes.startswith(b"%PDF-")
        and len(quotation.pdf_bytes) <= MAX_PDF_BYTES
    )
    for item in quotation.items:
        valid = valid and (
            bool(item.description.strip())
            and item.quantity.is_finite()
            and item.quantity > 0
            and item.unit_price is not None
            and item.unit_price.is_finite()
            and item.unit_price >= 0
        )
    if not valid:
        raise HTTPException(status_code=422, detail="Quotation is not ready to send")


def duplicate_attempt(error: IntegrityError, dialect: str) -> bool:
    if dialect == "postgresql":
        return (
            getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            == "send_attempts_quotation_id_key"
        )
    return (
        dialect == "sqlite"
        and getattr(error.orig, "sqlite_errorcode", None) == 2067
        and str(error.orig)
        == "UNIQUE constraint failed: send_attempts.quotation_id"
    )


@router.post("/{quotation_id}/send")
def send_quotation(
    quotation_id: UUID, approval: SendApproval, request: Request
) -> JSONResponse:
    if not request.app.state.settings.enable_demo_approval:
        raise HTTPException(status_code=503, detail="Demo approval is disabled")
    actor = request.headers.get("X-Demo-Actor", "")
    if actor not in {"pm", "sales"}:
        raise HTTPException(status_code=401, detail="Unknown demo actor")
    if actor != "pm":
        raise HTTPException(status_code=403, detail="PM approval is required")
    sender = request.app.state.telegram_sender
    if sender is None:
        raise HTTPException(status_code=503, detail="Telegram delivery unavailable")

    engine = request.app.state.engine
    provider = request.app.state.quotation_provider
    saved_id = str(quotation_id)
    attempt_id = str(uuid4())
    approved_at = datetime.now(timezone.utc)
    try:
        with integration_transaction(engine) as connection:
            previous = connection.execute(
                select(send_attempts.c.id)
                .where(send_attempts.c.quotation_id == saved_id)
            ).first()
            if previous is not None:
                raise HTTPException(
                    status_code=409, detail="Delivery already attempted"
                )
            quotation = provider.reserve_for_send(
                connection, saved_id, approval.expected_version
            )
            validate_quotation(quotation, saved_id, approval.expected_version)
            chat_id = connection.execute(
                select(telegram_updates.c.chat_id)
                .join(
                    enquiries,
                    enquiries.c.telegram_update_id == telegram_updates.c.update_id,
                )
                .where(enquiries.c.id == quotation.enquiry_id)
            ).scalar_one_or_none()
            if chat_id is None:
                raise HTTPException(status_code=422, detail="Original chat unavailable")
            connection.execute(
                send_attempts.insert().values(
                    id=attempt_id,
                    quotation_id=saved_id,
                    enquiry_id=quotation.enquiry_id,
                    version=quotation.version,
                    actor_id=actor,
                    role="pm",
                    approved_at=approved_at,
                    pdf_sha256=sha256(quotation.pdf_bytes).hexdigest(),
                    pdf_bytes=quotation.pdf_bytes,
                    status="pending",
                    updated_at=approved_at,
                )
            )
            # Includes in-flight delivery: there is no confirmed result yet.
            # A crash leaves this visible state and pending attempt for checking.
            connection.execute(
                enquiries.update().where(enquiries.c.id == quotation.enquiry_id)
                .values(status="unknown")
            )
    except HTTPException:
        raise
    except QuotationNotFound:
        raise HTTPException(status_code=404, detail="Quotation not found") from None
    except QuotationConflict:
        raise HTTPException(
            status_code=409, detail="Quotation is not sendable"
        ) from None
    except QuotationNotReady:
        raise HTTPException(
            status_code=422, detail="Quotation is not ready to send"
        ) from None
    except IntegrationUnavailable:
        raise HTTPException(
            status_code=503, detail="Saved quotation integration unavailable"
        ) from None
    except IntegrityError as error:
        if duplicate_attempt(error, engine.dialect.name):
            raise HTTPException(
                status_code=409, detail="Delivery already attempted"
            ) from None
        raise HTTPException(
            status_code=503, detail="Delivery storage unavailable"
        ) from None
    except Exception:
        raise HTTPException(
            status_code=503, detail="Delivery preparation failed"
        ) from None

    # The durable pending row blocks retries even if the process dies from here on.
    try:
        result = sender.send_pdf(chat_id, quotation.pdf_bytes)
        if result.status not in {"sent", "failed", "unknown"}:
            raise ValueError("Invalid delivery result")
    except Exception:
        result = DeliveryResult(status="unknown", error_code="unexpected_send_error")
    try:
        with integration_transaction(engine) as connection:
            connection.execute(
                send_attempts.update().where(send_attempts.c.id == attempt_id).values(
                    status=result.status,
                    provider_message_id=result.message_id,
                    safe_error_code=safe_error_code(result.error_code),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            connection.execute(
                enquiries.update()
                .where(enquiries.c.id == quotation.enquiry_id)
                .values(status=result.status)
            )
            provider.record_outcome(
                connection, saved_id, result.status, result.message_id
            )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "attempt_id": attempt_id,
                "status": "unknown",
                "detail": "Delivery outcome could not be saved",
            },
        )
    return JSONResponse(
        status_code={"sent": 200, "failed": 502, "unknown": 202}[result.status],
        content={"attempt_id": attempt_id, "status": result.status},
    )
