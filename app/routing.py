"""Persist conservative associations and explicit Staff assignment history."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Request
from sqlalchemy import select

from app.activity import record_activity, require_demo_staff
from app.database import enquiries, telegram_updates, message_links, enquiry_values, outgoing_messages, send_attempts
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
            enquiries.c.status.in_(["needs_review", "sent", "failed", "unknown"]))
        .order_by(enquiries.c.created_at.desc())).scalars())
    target = None
    if reply_to:
        target = connection.execute(select(message_links.c.enquiry_id).join(
            telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
        ).where(message_links.c.business_profile_id == identity,
                telegram_updates.c.chat_id == chat_id, telegram_updates.c.message_id == reply_to,
                message_links.c.status == "assigned")).scalar_one_or_none()
        if target is None:
            target = connection.execute(select(outgoing_messages.c.enquiry_id).join(
                enquiries, outgoing_messages.c.enquiry_id == enquiries.c.id
            ).join(telegram_updates, enquiries.c.telegram_update_id == telegram_updates.c.update_id)
                .where(outgoing_messages.c.business_profile_id == identity,
                       outgoing_messages.c.provider_message_id == str(reply_to),
                       outgoing_messages.c.status == "sent", telegram_updates.c.chat_id == chat_id)).scalar_one_or_none()
        if target is None:
            target = connection.execute(select(send_attempts.c.enquiry_id).distinct().join(
                enquiries, send_attempts.c.enquiry_id == enquiries.c.id
            ).join(telegram_updates, enquiries.c.telegram_update_id == telegram_updates.c.update_id)
                .where(enquiries.c.business_profile_id == identity, telegram_updates.c.chat_id == chat_id,
                       ((send_attempts.c.provider_message_id == str(reply_to)) &
                        ((send_attempts.c.status == "sent") | (send_attempts.c.pdf_status == "sent"))) |
                       ((send_attempts.c.summary_provider_message_id == str(reply_to)) &
                        (send_attempts.c.summary_status == "sent")))).scalar_one_or_none()
    decision, target = association(text, candidates, target, reply_expected=reply_to is not None)
    if decision == "new":
        target = new_enquiry(connection, {"update_id": update_id, "received_at": at}, identity)
        decision = "assigned"
    evidence = link_event(target, "system", decision, at)
    if reply_to is not None:
        evidence["reply_to_message_id"] = str(reply_to)
    connection.execute(message_links.insert().values(
        update_id=update_id, business_profile_id=identity, enquiry_id=target,
        status=decision, assigned_by="system", history=[evidence],
    ))
    if target:
        connection.execute(enquiries.update().where(enquiries.c.id == target, enquiries.c.status != "unknown")
                           .values(status="needs_review"))
        record_activity(connection, enquiry_id=target, action="telegram_received", result="received",
                        actor_id="system", role="system", actor_origin="system",
                        provider_reference=str(update_id), timestamp=at)


def assign_message(store, update_id, patch, actor, *, origin="staff", confirmation_update_id=None):
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
        identity = (store.get("enquiries", patch.get("enquiry_id", ""))["business_profile_id"]
                    if origin == "ai" else store.get("settings", "active_profile")["business_profile_id"])
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
        if origin == "ai":
            validate_confirmation(store, row, target, confirmation_update_id)
        status = "assigned" if target else "unrelated"
        entry = link_event(target, actor, action)
        if origin == "ai":
            entry["confirmation_update_id"] = str(confirmation_update_id)
        history = [*row["history"], entry]
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


def validate_confirmation(store, unresolved, target, confirmation_update_id):
    """A model-selected target is never evidence. Require a real customer reply."""
    if not isinstance(confirmation_update_id, str) or not confirmation_update_id.isdecimal():
        raise AppError("Customer confirmation evidence is required")
    row = store.connection.execute(select(message_links, telegram_updates).join(
        telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
    ).where(message_links.c.update_id == int(confirmation_update_id))).mappings().one_or_none()
    if (row is None or row['status'] != 'assigned' or row['enquiry_id'] != target or
            row['business_profile_id'] != unresolved['business_profile_id'] or
            row['chat_id'] != unresolved['chat_id'] or
            (row['received_at'], row['update_id']) <= (unresolved['received_at'], unresolved['update_id']) or
            not any(h.get('reply_to_message_id') == str(unresolved['message_id']) for h in row['history'])):
        raise AppError("Customer confirmation does not identify this unresolved message")
    # Exact stable reference and explicit association phrasing, not an AI interpretation.
    references = [target] + [q['number'] for q in store.list('quotations') if q['enquiryId'] == target]
    normalized = row['original_text'].strip().casefold().rstrip('.')
    if not any(normalized == 'this message is for ' + ref.casefold() for ref in references):
        raise AppError("Customer must explicitly confirm the enquiry reference")


def resolve_ai_assignment(store, enquiry_id, proposal):
    object_fields(proposal, {"update_id", "confirmation_update_id"})
    identity = proposal.get('update_id')
    if not isinstance(identity, str) or not identity.isdecimal():
        raise AppError("Invalid unresolved message reference")
    return assign_message(store, int(identity), {'action': 'assign', 'enquiry_id': enquiry_id},
                          'system', origin='ai', confirmation_update_id=proposal.get('confirmation_update_id'))
