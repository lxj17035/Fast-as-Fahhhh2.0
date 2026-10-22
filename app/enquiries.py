"""Read enquiry inbox and details for the supervised team demo."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from app.database import enquiries, telegram_updates

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


class EnquiryDetail(EnquirySummary):
    messages: list[OriginalMessage]


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
    )
