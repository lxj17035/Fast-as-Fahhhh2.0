"""Read enquiry inbox and details for the supervised team demo."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from app.database import activities, enquiries, send_attempts, telegram_updates, message_links
from app.xinjie_store import Store

router = APIRouter(prefix="/api/enquiries", tags=["enquiries"])


class EnquirySummary(BaseModel):
    id: str
    source: str
    status: str
    created_at: datetime
    telegram_chat_id: str
    original_text: str
    business_profile_id: str


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
    assigned_by: str = "legacy"
    assignment_history: list[dict] = Field(default_factory=list)


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
    retry_of_attempt_id: str | None
    can_retry: bool
    pdf_status: str | None = None
    summary_status: str | None = None
    summary_provider_message_id: str | None = None
    telegram_summary: str | None = None
    source_message_ids: list[str] | None = None


class ActivityRecord(BaseModel):
    id: str
    enquiry_id: str
    quotation_id: str | None
    version: int | None
    attempt_id: str | None
    timestamp: datetime
    actor_id: str | None
    role: str | None
    actor_origin: str
    action: str
    result: str
    provider_reference: str | None
    safe_error_code: str | None


class EnquiryDetail(EnquirySummary):
    messages: list[OriginalMessage]
    delivery_attempts: list[DeliveryAttempt]
    activity: list[ActivityRecord]


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
        business_profile_id=row["business_profile_id"],
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
            identity = Store(connection.engine, connection).get("settings", "active_profile")["business_profile_id"]
            statement = statement.where(enquiries.c.business_profile_id == identity)
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
            identity = Store(connection.engine, connection).get("settings", "active_profile")["business_profile_id"]
            statement = statement.where(enquiries.c.business_profile_id == identity)
            row = connection.execute(statement).mappings().one_or_none()
            messages = connection.execute(select(telegram_updates, message_links.c.assigned_by,
                                                  message_links.c.history).join(
                message_links, message_links.c.update_id == telegram_updates.c.update_id
            ).where(message_links.c.enquiry_id == str(enquiry_id))
                .order_by(telegram_updates.c.received_at, telegram_updates.c.update_id)).mappings().all()
            attempts = connection.execute(
                select(
                    send_attempts.c.id,
                    send_attempts.c.retry_of_attempt_id,
                    send_attempts.c.quotation_id,
                    send_attempts.c.version,
                    send_attempts.c.status,
                    send_attempts.c.approved_at,
                    send_attempts.c.updated_at,
                    send_attempts.c.provider_message_id,
                    send_attempts.c.safe_error_code,
                    send_attempts.c.summary_text,
                    send_attempts.c.pdf_status,
                    send_attempts.c.summary_status,
                    send_attempts.c.summary_provider_message_id,
                    send_attempts.c.source_message_ids,
                )
                .where(send_attempts.c.enquiry_id == str(enquiry_id))
                .order_by(send_attempts.c.approved_at, send_attempts.c.id)
            ).mappings().all()
            history = connection.execute(
                select(activities)
                .where(activities.c.enquiry_id == str(enquiry_id))
                .order_by(activities.c.timestamp, activities.c.id)
            ).mappings().all()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Enquiry storage unavailable"
        ) from None
    if row is None:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    consumed = {attempt["retry_of_attempt_id"] for attempt in attempts}
    blocked_quotes = {a["quotation_id"] for a in attempts if a["status"] != "failed"}
    return EnquiryDetail(
        **summary(row).model_dump(),
        messages=[
            OriginalMessage(
                update_id=str(message["update_id"]),
                message_id=str(message["message_id"]),
                chat_id=str(message["chat_id"]),
                text=message["original_text"],
                received_at=utc_timestamp(message["received_at"]),
                assigned_by=message.get("assigned_by", "legacy"),
                assignment_history=message.get("history", []),
            )
            for message in (messages or [row])
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
                telegram_summary=attempt["summary_text"],
                pdf_status=attempt["pdf_status"], summary_status=attempt["summary_status"],
                summary_provider_message_id=attempt["summary_provider_message_id"],
                source_message_ids=attempt["source_message_ids"],
                requires_verification=attempt["status"] in {"pending", "unknown"},
                retry_of_attempt_id=attempt["retry_of_attempt_id"],
                can_retry=(attempt["status"] == "failed" and attempt["id"] not in consumed
                           and attempt["quotation_id"] not in blocked_quotes),
            )
            for attempt in attempts
        ],
        activity=[
            ActivityRecord(**{
                **event,
                "timestamp": utc_timestamp(event["timestamp"]),
            })
            for event in history
        ],
    )
