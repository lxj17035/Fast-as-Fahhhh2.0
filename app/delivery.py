"""Controlled demo delivery of the saved quotation version approved by PM."""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.activity import record_activity
from app.database import enquiries, send_attempts, telegram_updates
from app.quotation_contract import (
    IntegrationUnavailable,
    QuotationConflict,
    QuotationNotFound,
    QuotationNotReady,
    SavedQuotation,
)
from app.telegram_client import DeliveryResult
from app.xinjie_store import Store, integration_transaction
from backend.errors import safe_delivery_error_code as safe_error_code

router = APIRouter(prefix="/api/quotations", tags=["delivery"])
MAX_PDF_BYTES = 10 * 1024 * 1024


class SendApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]
    approved: Literal[True]
    retry_of_attempt_id: UUID | None = None

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
            in {"send_attempts_initial_unique", "send_attempts_retry_unique"}
        )
    return (
        dialect == "sqlite"
        and getattr(error.orig, "sqlite_errorcode", None) == 2067
        and str(error.orig) in {
            "UNIQUE constraint failed: send_attempts.quotation_id",
            "UNIQUE constraint failed: send_attempts.retry_of_attempt_id",
        }
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
            identity = Store(engine, connection).get("settings", "active_profile")["business_profile_id"]
            previous = connection.execute(
                select(send_attempts.c.id, send_attempts.c.status,
                       send_attempts.c.retry_of_attempt_id, enquiries.c.business_profile_id)
                .join(enquiries, send_attempts.c.enquiry_id == enquiries.c.id)
                .where(send_attempts.c.quotation_id == saved_id)
            ).mappings().all()
            if any(row["business_profile_id"] != identity for row in previous):
                raise HTTPException(status_code=404, detail="Quotation not found in this business profile")
            retry_of = str(approval.retry_of_attempt_id) if approval.retry_of_attempt_id else None
            if previous:
                # Never retry a success, an active upload or an ambiguous outcome.
                # Referencing the exact failed attempt prevents a delayed/replayed
                # approval from silently becoming a further retry after another failure.
                blocked = any(row["status"] != "failed" for row in previous)
                consumed = {row["retry_of_attempt_id"] for row in previous}
                eligible = any(row["id"] == retry_of for row in previous)
                if blocked or not eligible or retry_of in consumed:
                    raise HTTPException(status_code=409,
                        detail="Explicit approval of the current failed attempt is required; pending, sent or unknown delivery cannot be retried")
            elif retry_of is not None:
                raise HTTPException(status_code=409, detail="Failed attempt not found for this quotation")
            quotation = provider.reserve_for_send(
                connection, saved_id, approval.expected_version
            )
            validate_quotation(quotation, saved_id, approval.expected_version)
            source = connection.execute(
                select(telegram_updates.c.chat_id, enquiries.c.business_profile_id)
                .join(
                    enquiries,
                    enquiries.c.telegram_update_id == telegram_updates.c.update_id,
                )
                .where(enquiries.c.id == quotation.enquiry_id)
            ).mappings().one_or_none()
            if source is None:
                raise HTTPException(status_code=422, detail="Original chat unavailable")
            if source["business_profile_id"] != identity:
                raise HTTPException(status_code=404, detail="Quotation not found in this business profile")
            chat_id = source["chat_id"]
            connection.execute(
                send_attempts.insert().values(
                    id=attempt_id,
                    quotation_id=saved_id,
                    retry_of_attempt_id=retry_of,
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
            activity = {
                "enquiry_id": quotation.enquiry_id,
                "quotation_id": saved_id,
                "version": quotation.version,
                "attempt_id": attempt_id,
                "actor_id": actor,
                "role": "pm",
                "actor_origin": "simulated",
            }
            record_activity(
                connection, **activity, action="pm_approved", result="approved"
            )
            record_activity(
                connection, **activity, action="pdf_send_attempted", result="pending"
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
            record_activity(
                connection,
                **activity,
                action={
                    "sent": "pdf_send_succeeded",
                    "failed": "pdf_send_failed",
                    "unknown": "delivery_unknown",
                }[result.status],
                result=result.status,
                provider_reference=result.message_id,
                safe_error_code=safe_error_code(result.error_code),
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
