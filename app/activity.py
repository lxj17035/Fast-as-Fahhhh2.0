"""Append actual application events in the transaction that performs the work."""

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from sqlalchemy.engine import Connection

from app.database import activities

ACTIONS = frozenset({
    "telegram_received",
    "enquiry_created",
    "quotation_draft_created",
    "quotation_updated",
    "pm_approved",
    "pdf_send_attempted",
    "pdf_send_succeeded",
    "pdf_send_failed",
    "delivery_unknown",
})
SAFE_ERROR_CODES = frozenset({
    "invalid_response",
    "telegram_timeout",
    "telegram_transport_error",
    "unconfirmed_response",
    "unexpected_send_error",
    "unclassified_delivery_error",
})


def record_activity(
    connection: Connection,
    *,
    enquiry_id: str,
    action: str,
    result: str,
    quotation_id: str | None = None,
    version: int | None = None,
    attempt_id: str | None = None,
    actor_id: str | None = None,
    role: str | None = None,
    actor_origin: str = "unknown",
    provider_reference: str | None = None,
    safe_error_code: str | None = None,
    timestamp: datetime | None = None,
    event_id: str | None = None,
) -> str:
    """Insert only; callers guard duplicate actions and own commit or rollback."""
    if action not in ACTIONS:
        raise ValueError("Unsupported activity action")
    if actor_origin not in {"system", "simulated", "unknown"}:
        raise ValueError("Unsupported actor origin")
    if not result or len(result) > 40:
        raise ValueError("Invalid activity result")
    if actor_id is not None and len(actor_id) > 80:
        raise ValueError("Invalid activity actor")
    if role is not None and len(role) > 20:
        raise ValueError("Invalid activity role")
    if provider_reference is not None and not re.fullmatch(
        r"[0-9]{1,100}", str(provider_reference)
    ):
        provider_reference = None
    if safe_error_code is not None and (
        safe_error_code not in SAFE_ERROR_CODES
        and not re.fullmatch(r"telegram_4[0-9]{2}", safe_error_code)
    ):
        safe_error_code = "unclassified_delivery_error"
    recorded_at = timestamp if timestamp is not None else datetime.now(timezone.utc)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    identity = str(UUID(event_id)) if event_id is not None else str(uuid4())
    connection.execute(activities.insert().values(
        id=identity,
        enquiry_id=str(UUID(enquiry_id)),
        quotation_id=str(UUID(quotation_id)) if quotation_id else None,
        version=version,
        attempt_id=str(UUID(attempt_id)) if attempt_id else None,
        timestamp=recorded_at.astimezone(timezone.utc),
        actor_id=actor_id,
        role=role,
        actor_origin=actor_origin,
        action=action,
        result=result,
        provider_reference=(
            str(provider_reference) if provider_reference is not None else None
        ),
        safe_error_code=safe_error_code,
    ))
    return identity


def optional_demo_actor(request: Request) -> dict:
    actor = request.headers.get("X-Demo-Actor")
    if actor is None:
        return {"actor_id": None, "role": None, "actor_origin": "unknown"}
    if actor not in {"pm", "sales"}:
        raise HTTPException(status_code=401, detail="Unknown demo actor")
    if not request.app.state.settings.enable_demo_approval:
        raise HTTPException(status_code=503, detail="Demo approval is disabled")
    return {"actor_id": actor, "role": actor, "actor_origin": "simulated"}
