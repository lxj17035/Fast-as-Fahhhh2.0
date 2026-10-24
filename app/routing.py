"""Persist conservative associations and explicit Staff assignment history."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Request
from sqlalchemy import select

from app.activity import record_activity, require_demo_staff
from app.database import enquiries, telegram_updates, message_links, enquiry_values
from app.xinjie_store import Store, integration_transaction
from backend.errors import AppError, object_fields
from backend.routing import association
from backend.settings import require_profile

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


def link_event(enquiry_id, actor, action, at=None):
    return {"enquiry_id": enquiry_id, "actor": actor, "action": action,
            "timestamp": (at or datetime.now(timezone.utc)).isoformat()}


def new_enquiry(connection, receipt, identity):
    value = enquiry_values(receipt["update_id"], receipt["received_at"], identity)
    connection.execute(enquiries.insert().values(**value))
    record_activity(connection, enquiry_id=value["id"], action="enquiry_created", result="created",
                    actor_id="system", role="system", actor_origin="system")
    return value["id"]


def route_receipt(connection, update_id, message_id, chat_id, text, at, identity, reply_to=None):
    candidates = list(connection.execute(select(enquiries.c.id).join(
        telegram_updates, enquiries.c.telegram_update_id == telegram_updates.c.update_id
    ).where(enquiries.c.business_profile_id == identity, telegram_updates.c.chat_id == chat_id,
            enquiries.c.status.in_(["needs_review", "sent", "failed"]))
        .order_by(enquiries.c.created_at.desc())).scalars())
    target = None
    if reply_to:
        target = connection.execute(select(message_links.c.enquiry_id).join(
            telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
        ).where(message_links.c.business_profile_id == identity,
                telegram_updates.c.chat_id == chat_id, telegram_updates.c.message_id == reply_to,
                message_links.c.status == "assigned")).scalar_one_or_none()
    decision, target = association(text, candidates, target)
    if decision == "new":
        target = new_enquiry(connection, {"update_id": update_id, "received_at": at}, identity)
        decision = "assigned"
    connection.execute(message_links.insert().values(
        update_id=update_id, business_profile_id=identity, enquiry_id=target,
        status=decision, assigned_by="system", history=[link_event(target, "system", decision, at)],
    ))
    if target:
        record_activity(connection, enquiry_id=target, action="telegram_received", result="received",
                        actor_id="system", role="system", actor_origin="system",
                        provider_reference=str(update_id), timestamp=at)


def assign_message(store, update_id, patch, actor, *, origin="staff"):
    object_fields(patch, {"action", "enquiry_id"})
    action = patch.get("action")
    if action not in {"assign", "new", "unrelated"} or (origin == "ai" and action != "assign"):
        raise AppError("Unsupported assignment action")
    with store.transaction():
        connection = store.connection
        row = connection.execute(select(message_links, telegram_updates).join(
            telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
        ).where(message_links.c.update_id == update_id)).mappings().one_or_none()
        if row is None:
            raise AppError("Message not found", 404)
        identity = store.get("settings", "active_profile")["business_profile_id"]
        require_profile(row, identity)
        if row["status"] != "needs_assignment":
            raise AppError("Assignment is already resolved; confirmed history is retained", 409)
        target = None
        if action == "assign":
            try:
                target = str(UUID(patch.get("enquiry_id", "")))
            except (ValueError, TypeError, AttributeError):
                raise AppError("A valid enquiry_id is required") from None
            enquiry = require_profile(store.get("enquiries", target), identity)
            if str(row["chat_id"]) != enquiry["chatId"]:
                raise AppError("Message and enquiry must have the same original chat", 422)
        elif action == "new":
            target = new_enquiry(connection, row, identity)
        status = "assigned" if target else "unrelated"
        history = [*row["history"], link_event(target, actor, action)]
        connection.execute(message_links.update().where(message_links.c.update_id == update_id).values(
            enquiry_id=target, status=status, assigned_by=origin, history=history))
        if target:
            record_activity(connection, enquiry_id=target, action="message_assigned", result="assigned",
                            actor_id=actor, role=actor, actor_origin="simulated" if origin == "staff" else "system",
                            provider_reference=str(update_id))
        return {"update_id": str(update_id), "enquiry_id": target, "status": status,
                "assigned_by": origin, "history": history}


@router.get("")
def list_assignments(request: Request):
    engine = request.app.state.engine
    with engine.connect() as connection:
        identity = Store(engine, connection).get("settings", "active_profile")["business_profile_id"]
        rows = connection.execute(select(message_links, telegram_updates).join(
            telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
        ).where(message_links.c.business_profile_id == identity,
                message_links.c.status == "needs_assignment")
            .order_by(telegram_updates.c.received_at, telegram_updates.c.update_id)).mappings()
        return {"items": [{"update_id": str(r["update_id"]), "chat_id": str(r["chat_id"]),
                           "text": r["original_text"], "business_profile_id": r["business_profile_id"],
                           "status": r["status"], "history": r["history"]} for r in rows]}


@router.post("/{update_id}")
def resolve_assignment(update_id: int, request: Request, patch: dict = Body(...)):
    actor = require_demo_staff(request)
    result = assign_message(Store(request.app.state.engine), update_id, patch, actor)
    if result["enquiry_id"]:
        request.app.state.automatic_drafting.run(update_id)
    return result
