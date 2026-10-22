"""Receive authenticated Telegram text updates without calling Telegram."""

import json
from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.database import save_update

router = APIRouter()
MAX_BODY_BYTES = 64 * 1024
MAX_INTEGER = 2**63 - 1


class TelegramChat(BaseModel):
    model_config = ConfigDict(strict=True)
    id: Annotated[int, Field(ge=-(2**63), le=MAX_INTEGER)]

    @field_validator("id")
    @classmethod
    def nonzero_id(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Chat ID must be nonzero")
        return value


class TelegramMessage(BaseModel):
    model_config = ConfigDict(strict=True)
    message_id: Annotated[int, Field(gt=0, le=MAX_INTEGER)]
    chat: TelegramChat
    text: Annotated[str, Field(min_length=1, max_length=4096)] | None = None

    @field_validator("text")
    @classmethod
    def valid_text(cls, value: str | None) -> str | None:
        if value is not None:
            if not value.strip() or "\x00" in value:
                raise ValueError("Text must be nonblank and contain no null characters")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise ValueError("Text must be valid Unicode") from None
        return value


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(strict=True)
    update_id: Annotated[int, Field(ge=0, le=MAX_INTEGER)]
    message: TelegramMessage | None = None


@router.post("/api/webhooks/telegram")
async def receive_update(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected_secret = request.app.state.settings.telegram_webhook_secret
    if not compare_digest(
        supplied_secret.encode("utf-8"), expected_secret.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook body too large")
        body.extend(chunk)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    try:
        update = TelegramUpdate.model_validate(payload)
    except ValidationError:
        # Pydantic's default errors can include customer text; never return those.
        raise HTTPException(status_code=422, detail="Invalid Telegram update") from None
    if update.message is None or update.message.text is None:
        return {"status": "ignored"}

    try:
        stored = await run_in_threadpool(
            save_update,
            request.app.state.engine,
            update.update_id,
            update.message.message_id,
            update.message.chat.id,
            update.message.text,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Message storage unavailable"
        ) from None
    # Run only after receipt/enquiry commit and response creation. Duplicates may
    # retry an interrupted draft; DraftService returns existing PM-edited drafts.
    background_tasks.add_task(request.app.state.automatic_drafting.run, update.update_id)
    return {"status": "received" if stored else "duplicate"}
