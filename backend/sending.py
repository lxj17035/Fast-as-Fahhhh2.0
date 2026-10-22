"""Explicit PM approval, one saved PDF version, and guarded external delivery."""
from datetime import datetime, timezone
import re
from uuid import uuid4

from .errors import AppError, object_fields, text
from .quotations import expected_version
from .telegram_delivery import DeliveryResult


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class SendService:
    def __init__(self, store, quotations, pdfs, sender):
        self.store, self.quotations, self.pdfs, self.sender = store, quotations, pdfs, sender

    def response(self, quote):
        attempt = self.store.get("send_attempts", quote["sendAttemptId"])
        status = {"sending": 202, "sent": 200, "send_failed": 502, "send_uncertain": 202}[quote["status"]]
        return status, {"quotationId": quote["id"], "version": quote["version"],
                        "attemptId": attempt["id"], "status": quote["status"],
                        "providerReference": attempt.get("providerReference"),
                        "error": attempt.get("error"), "retryAfter": attempt.get("retryAfter"),
                        "readConfirmed": False}

    def send(self, quotation_id, body):
        object_fields(body, {"version", "previewedVersion", "actor", "role", "approved", "retry"})
        if body.get("role") != "pm":
            raise AppError("Only the simulated PM role may approve sending", 403)
        if body.get("approved") is not True:
            raise AppError("Explicit approval is required before sending")
        actor = text(body.get("actor"), "actor", required=True)
        version = body.get("version")
        if type(version) is not int or version < 1 or type(body.get("previewedVersion")) is not int:
            raise AppError("version and previewedVersion must be positive integers")
        if body["previewedVersion"] != version:
            raise AppError("Preview the current quotation version before approval", 409)
        if not isinstance(body.get("retry", False), bool):
            raise AppError("retry must be a boolean")
        with self.store.transaction():
            quote = self.quotations.get(quotation_id)
            expected_version(quote, version)
            if quote["status"] in ("sending", "sent") and quote.get("sendAttemptId"):
                return self.response(quote)
            if quote["status"] == "send_uncertain":
                raise AppError("Delivery is uncertain; check the original chat before any resend", 409)
            if quote["status"] == "send_failed" and body.get("retry") is not True:
                raise AppError("A known failure requires a new explicit approval with retry=true", 409)
            self.quotations.validate_for_send(quotation_id, version, "pm")
            if not self.sender.configured:
                raise AppError("TELEGRAM_BOT_TOKEN is not configured; no document was sent", 503)
            enquiry = self.store.get("enquiries", quote["enquiryId"])
            chat_id = str(enquiry.get("chatId", ""))
            if enquiry.get("source") != "telegram" or not re.fullmatch(r"-?[1-9][0-9]*", chat_id):
                raise AppError("The quotation has no original Telegram recipient")
            try:
                self.store.get("pdfs", f"{quotation_id}:{version}")
            except AppError as error:
                if error.status != 404:
                    raise
                raise AppError("Preview the saved PDF before approving this version", 409) from None
            pdf, _ = self.pdfs.get(quotation_id, version)
            quote = self.quotations.begin_send(quotation_id, version, actor, "pm")
            attempt_id = uuid4().hex
            quote["sendAttemptId"] = attempt_id
            quote.pop("sendError", None)
            self.store.put("quotations", quotation_id, quote)
            attempt = {"id": attempt_id, "quotationId": quotation_id, "enquiryId": quote["enquiryId"],
                       "version": version, "actor": actor, "role": "pm", "status": "pending",
                       "createdAt": timestamp(), "chatId": chat_id}
            self.store.put("send_attempts", attempt_id, attempt)
        # No database transaction/lock is held while the external request runs.
        try:
            result = self.sender.send_document(chat_id, pdf, quote["number"] + ".pdf")
            if not isinstance(result, DeliveryResult) or result.outcome not in ("accepted", "failed", "uncertain"):
                raise ValueError()
        except Exception:
            result = DeliveryResult("uncertain", error="Delivery outcome is unknown; check the original chat")
        try:
            with self.store.transaction():
                quote = self.quotations.record_send_result(quotation_id, result.outcome, result.reference)
                quote["sendError"] = result.error
                self.store.put("quotations", quotation_id, quote)
                attempt.update(status=result.outcome, providerReference=result.reference,
                               error=result.error, retryAfter=result.retry_after, completedAt=timestamp())
                self.store.put("send_attempts", attempt_id, attempt)
                enquiry = self.store.get("enquiries", quote["enquiryId"])
                enquiry["status"] = {"accepted": "sent", "failed": "failed", "uncertain": "unknown"}[result.outcome]
                self.store.put("enquiries", enquiry["id"], enquiry)
                return self.response(quote)
        except Exception:
            # A committed pending attempt blocks another external call even if
            # persistence failed after Telegram accepted the upload.
            raise AppError("Send result could not be recorded; check the original chat before retrying", 503) from None
