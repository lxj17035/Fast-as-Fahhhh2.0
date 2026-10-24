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
from app.database import enquiries, send_attempts, telegram_updates, message_links
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
        and isinstance(quotation.telegram_summary, str)
        and 0 < len(quotation.telegram_summary.strip()) <= 4000
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
                select(send_attempts, enquiries.c.business_profile_id)
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
            prior = next((row for row in previous if row["id"] == retry_of), None)
            resume_summary = prior is not None and prior["pdf_status"] == "sent"
            reserve = (getattr(provider, "reserve_summary_retry", provider.reserve_for_send)
                       if resume_summary else provider.reserve_for_send)
            quotation = reserve(connection, saved_id, approval.expected_version)
            if resume_summary and (quotation.version != prior["version"] or
                    sha256(quotation.pdf_bytes).hexdigest() != prior["pdf_sha256"] or
                    quotation.telegram_summary != prior["summary_text"] or
                    list(quotation.source_message_ids or []) != list(prior["source_message_ids"] or [])):
                raise HTTPException(status_code=409, detail="Accepted PDF and summary snapshot cannot change")
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
                    summary_text=quotation.telegram_summary,
                    source_message_ids=list(quotation.source_message_ids) if quotation.source_message_ids is not None else None,
                    pdf_status="sent" if resume_summary else "pending",
                    provider_message_id=prior["provider_message_id"] if resume_summary else None,
                    summary_status="pending",
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
                connection, **activity, action="summary_send_attempted" if resume_summary else "pdf_send_attempted", result="pending"
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

    # Persist PDF acceptance before attempting its summary. Any crash/save failure
    # leaves a pending hold; accepted PDFs are never blindly uploaded again.
    pdf_result = (DeliveryResult("sent", message_id=prior["provider_message_id"])
                  if resume_summary else safe_send(lambda: sender.send_pdf(chat_id, quotation.pdf_bytes)))
    summary_result = None
    if pdf_result.status == "sent":
        try:
            with integration_transaction(engine) as connection:
                connection.execute(send_attempts.update().where(send_attempts.c.id == attempt_id).values(
                    pdf_status="sent", provider_message_id=pdf_result.message_id,
                    updated_at=datetime.now(timezone.utc)))
        except Exception:
            return JSONResponse(status_code=503, content={"attempt_id": attempt_id, "status": "unknown",
                                "detail": "PDF outcome could not be saved; verify delivery"})
        summary_result = safe_send(lambda: sender.send_text(chat_id, quotation.telegram_summary))
        result = summary_result
    else:
        result = pdf_result
    try:
        with integration_transaction(engine) as connection:
            connection.execute(
                send_attempts.update().where(send_attempts.c.id == attempt_id).values(
                    status=result.status,
                    provider_message_id=pdf_result.message_id,
                    pdf_status=pdf_result.status,
                    summary_status=summary_result.status if summary_result else "not_attempted",
                    summary_provider_message_id=summary_result.message_id if summary_result else None,
                    safe_error_code=safe_error_code(result.error_code),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            enquiry_status = result.status
            if result.status == "sent" and quotation.source_message_ids is not None:
                current = connection.execute(select(message_links.c.update_id).join(
                    telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
                ).where(message_links.c.enquiry_id == quotation.enquiry_id)
                    .order_by(telegram_updates.c.received_at, telegram_updates.c.update_id)).scalars().all()
                pending = connection.execute(select(message_links.c.update_id).join(
                    telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
                ).where(message_links.c.business_profile_id == source["business_profile_id"],
                        telegram_updates.c.chat_id == chat_id, message_links.c.status == "needs_assignment")
                    .limit(1)).first()
                if [str(i) for i in current] != list(quotation.source_message_ids) or pending is not None:
                    enquiry_status = "needs_review"
            connection.execute(
                enquiries.update()
                .where(enquiries.c.id == quotation.enquiry_id)
                .values(status=enquiry_status)
            )
            provider.record_outcome(
                connection, saved_id, result.status, pdf_result.message_id
            )
            record_activity(
                connection,
                **activity,
                action="pdf_reused" if resume_summary else {
                    "sent": "pdf_send_succeeded",
                    "failed": "pdf_send_failed",
                    "unknown": "delivery_unknown",
                }[pdf_result.status],
                result=pdf_result.status,
                provider_reference=pdf_result.message_id,
                safe_error_code=safe_error_code(pdf_result.error_code),
            )
            if summary_result:
                record_activity(connection, **activity, action="summary_send_" + summary_result.status,
                                result=summary_result.status, provider_reference=summary_result.message_id,
                                safe_error_code=safe_error_code(summary_result.error_code))
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


def safe_send(send):
    try:
        result = send()
        if not isinstance(result, DeliveryResult) or result.status not in {"sent", "failed", "unknown"}:
            raise ValueError("Invalid delivery result")
        if result.status == "sent" and (not isinstance(result.message_id, str) or
                not result.message_id.isdecimal() or int(result.message_id) <= 0):
            raise ValueError("Accepted message reference required")
        return result
    except Exception:
        return DeliveryResult("unknown", error_code="unexpected_send_error")
