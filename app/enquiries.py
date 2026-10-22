"""Read enquiry inbox and details for the supervised team demo."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from app.database import enquiries, send_attempts, telegram_updates

router = APIRouter(prefix="/api/enquiries", tags=["enquiries"])


class EnquirySummary(BaseModel):
    id: str
    source: str
    status: str
    created_at: datetime
    telegram_chat_id: str
    original_text: str


class EnquiryPage(BaseModel):
    items: list[EnquirySummary]
    limit: int
    offset: int


class OriginalMessage(BaseModel):
    update_id: str
    message_id: str
    chat_id: str
    text: str
    received_at: datetime


class DeliveryAttempt(BaseModel):
    """Pending means processing or unresolved; never automatically retry it."""

    attempt_id: str
    quotation_id: str
    version: int
    status: str
    approved_at: datetime
    updated_at: datetime
    provider_message_id: str | None
    safe_error_code: str | None
    requires_verification: bool


class EnquiryDetail(EnquirySummary):
    messages: list[OriginalMessage]
    delivery_attempts: list[DeliveryAttempt]


def utc_timestamp(value: datetime) -> datetime:
    # SQLite drops timezone information; all timestamps are written in UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def summary(row: RowMapping) -> EnquirySummary:
    return EnquirySummary(
        id=row["id"],
        source=row["source"],
        status=row["status"],
        created_at=utc_timestamp(row["created_at"]),
        telegram_chat_id=str(row["chat_id"]),
        original_text=row["original_text"],
    )


def enquiry_query():
    return select(enquiries, telegram_updates).join(
        telegram_updates,
        enquiries.c.telegram_update_id == telegram_updates.c.update_id,
    )


@router.get("", response_model=EnquiryPage)
def list_enquiries(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
) -> EnquiryPage:
    statement = (
        enquiry_query()
        .order_by(enquiries.c.created_at.desc(), enquiries.c.id.desc())
        .limit(limit)
        .offset(offset)
    )
    try:
        with request.app.state.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Enquiry storage unavailable"
        ) from None
    return EnquiryPage(items=[summary(row) for row in rows], limit=limit, offset=offset)


@router.get("/{enquiry_id}", response_model=EnquiryDetail)
def get_enquiry(enquiry_id: UUID, request: Request) -> EnquiryDetail:
    statement = enquiry_query().where(enquiries.c.id == str(enquiry_id))
    try:
        with request.app.state.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            attempts = connection.execute(
                select(
                    send_attempts.c.id,
                    send_attempts.c.quotation_id,
                    send_attempts.c.version,
                    send_attempts.c.status,
                    send_attempts.c.approved_at,
                    send_attempts.c.updated_at,
                    send_attempts.c.provider_message_id,
                    send_attempts.c.safe_error_code,
                )
                .where(send_attempts.c.enquiry_id == str(enquiry_id))
                .order_by(send_attempts.c.approved_at, send_attempts.c.id)
            ).mappings().all()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Enquiry storage unavailable"
        ) from None
    if row is None:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    return EnquiryDetail(
        **summary(row).model_dump(),
        messages=[
            OriginalMessage(
                update_id=str(row["update_id"]),
                message_id=str(row["message_id"]),
                chat_id=str(row["chat_id"]),
                text=row["original_text"],
                received_at=utc_timestamp(row["received_at"]),
            )
        ],
        delivery_attempts=[
            DeliveryAttempt(
                attempt_id=attempt["id"],
                quotation_id=attempt["quotation_id"],
                version=attempt["version"],
                status=attempt["status"],
                approved_at=utc_timestamp(attempt["approved_at"]),
                updated_at=utc_timestamp(attempt["updated_at"]),
                provider_message_id=attempt["provider_message_id"],
                safe_error_code=attempt["safe_error_code"],
                requires_verification=attempt["status"] in {"pending", "unknown"},
            )
            for attempt in attempts
        ],
    )
