"""Explicit Staff-authored conversation actions, independent of HTTP."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import outgoing_messages, message_links, telegram_updates, send_attempts
from app.activity import record_activity
from app.telegram_client import DeliveryResult
from backend.errors import AppError, object_fields, text, safe_delivery_error_code
from backend.settings import require_profile


def serialize(row):
    return {key: (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
            if isinstance(value, datetime) else value for key, value in row.items()}


class ConversationService:
    def __init__(self, store, sender=None):
        self.store, self.sender = store, sender

    def list(self, enquiry_id):
        with self.store.reading() as connection:
            identity = self.store.get("settings", "active_profile")["business_profile_id"]
            require_profile(self.store.get("enquiries", enquiry_id), identity)
            received = connection.execute(select(telegram_updates, message_links.c.assigned_by).join(
                message_links, message_links.c.update_id == telegram_updates.c.update_id
            ).where(message_links.c.enquiry_id == enquiry_id)).mappings().all()
            outgoing = connection.execute(select(outgoing_messages).where(
                outgoing_messages.c.enquiry_id == enquiry_id)).mappings().all()
            deliveries = connection.execute(select(send_attempts).where(
                send_attempts.c.enquiry_id == enquiry_id).order_by(send_attempts.c.approved_at)).mappings().all()
        items = [{"id": "in-" + str(r["update_id"]), "direction": "incoming", "actor": "customer",
                  "text": r["original_text"], "status": "received", "created_at": r["received_at"],
                  "provider_message_id": str(r["message_id"]), "assigned_by": r["assigned_by"]} for r in received]
        items += [{**dict(r), "direction": "outgoing"} for r in outgoing]
        by_id = {row['id']: row for row in deliveries}
        for row in deliveries:
            prior = by_id.get(row['retry_of_attempt_id'])
            if not prior or prior.get('pdf_status') != 'sent':
                items.append({'id': 'pdf-' + row['id'], 'direction': 'outgoing', 'actor': row['actor_id'],
                              'kind': 'quotation_pdf', 'text': 'Quotation PDF', 'version': row['version'],
                              'quotation_id': row['quotation_id'], 'status': row.get('pdf_status') or row['status'],
                              'provider_message_id': row['provider_message_id'], 'created_at': row['approved_at']})
            if row['summary_text'] and row.get('summary_status') not in {None, 'not_attempted'}:
                items.append({'id': 'summary-' + row['id'], 'direction': 'outgoing', 'actor': row['actor_id'],
                              'kind': 'quotation_summary', 'text': row['summary_text'], 'version': row['version'],
                              'quotation_id': row['quotation_id'], 'status': row['summary_status'],
                              'provider_message_id': row['summary_provider_message_id'], 'created_at': row['updated_at']})
        # All timestamps are written UTC; SQLite's adapter drops the tz marker.
        for item in items:
            if item["created_at"].tzinfo is None:
                item["created_at"] = item["created_at"].replace(tzinfo=timezone.utc)
        items.sort(key=lambda item: (item["created_at"], item["id"]))
        return {"items": [serialize(item) for item in items]}

    def send(self, enquiry_id, patch, actor):
        if actor not in {"sales", "pm"}:
            raise AppError("Only Staff may explicitly send a message", 403)
        object_fields(patch, {"text", "request_id"})
        content = text(patch.get("text"), "text", required=True, limit=4000)
        try:
            request_id = str(UUID(patch.get("request_id", "")))
        except (ValueError, TypeError, AttributeError):
            raise AppError("A valid request_id is required") from None
        if self.sender is None:
            raise AppError("Telegram delivery unavailable", 503)
        with self.store.transaction():
            identity = self.store.get("settings", "active_profile")["business_profile_id"]
            enquiry = require_profile(self.store.get("enquiries", enquiry_id), identity)
            existing = self.store.connection.execute(select(outgoing_messages).where(
                outgoing_messages.c.business_profile_id == identity,
                outgoing_messages.c.request_id == request_id)).mappings().one_or_none()
            if existing:
                if existing["text"] != content or existing["enquiry_id"] != enquiry_id:
                    raise AppError("request_id already belongs to a different message", 409)
                return serialize(existing)
            now = datetime.now(timezone.utc)
            message = {"id": str(uuid4()), "enquiry_id": enquiry_id,
                       "business_profile_id": identity, "request_id": request_id, "actor": actor,
                       "text": content, "status": "pending", "provider_message_id": None,
                       "safe_error_code": None, "created_at": now, "updated_at": now}
            self.store.connection.execute(outgoing_messages.insert().values(**message))
            record_activity(self.store.connection, enquiry_id=enquiry_id, action="staff_message_requested",
                            result="pending", actor_id=actor, role=actor, actor_origin="simulated")
        try:
            result = self.sender.send_text(int(enquiry["chatId"]), content)
            if not isinstance(result, DeliveryResult) or result.status not in {"sent", "failed", "unknown"}:
                raise ValueError("Invalid provider outcome")
            if result.message_id is not None and (not result.message_id.isdecimal() or int(result.message_id) <= 0):
                raise ValueError("Invalid provider message reference")
            if result.status == "sent" and result.message_id is None:
                raise ValueError("Missing accepted message reference")
        except Exception:
            result = DeliveryResult("unknown", error_code="unexpected_send_error")
        message.update(status=result.status, provider_message_id=result.message_id,
                       safe_error_code=safe_delivery_error_code(result.error_code), updated_at=datetime.now(timezone.utc))
        try:
            with self.store.transaction():
                self.store.connection.execute(outgoing_messages.update().where(
                    outgoing_messages.c.id == message["id"]).values(
                        status=message["status"], provider_message_id=message["provider_message_id"],
                        safe_error_code=message["safe_error_code"], updated_at=message["updated_at"]))
                record_activity(self.store.connection, enquiry_id=enquiry_id,
                                action="staff_message_" + result.status, result=result.status,
                                actor_id=actor, role=actor, actor_origin="simulated",
                                provider_reference=result.message_id, safe_error_code=message["safe_error_code"])
        except SQLAlchemyError:
            # The committed pending record remains a hold against request replay.
            return {"id": message["id"], "status": "unknown", "requires_verification": True}
        return serialize(message)
