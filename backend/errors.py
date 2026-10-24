import re


class AppError(Exception):
    def __init__(self, message, status=422, fields=None):
        super().__init__(message)
        self.status = status
        self.fields = fields or {}


def text(value, field, *, required=False, limit=500):
    if not isinstance(value, str) or len(value) > limit:
        raise AppError(f"{field} must be text of at most {limit} characters")
    value = value.strip()
    if required and not value:
        raise AppError(f"{field} is required")
    return value


def object_fields(value, allowed):
    if not isinstance(value, dict):
        raise AppError("A JSON object is required")
    unknown = set(value) - set(allowed)
    if unknown:
        raise AppError("Unknown fields: " + ", ".join(sorted(unknown)))


def safe_delivery_error_code(value):
    if value is None or value in {
        "invalid_response", "telegram_timeout", "telegram_transport_error",
        "unconfirmed_response", "unexpected_send_error",
    }:
        return value
    if isinstance(value, str) and re.fullmatch(r"telegram_4[0-9]{2}", value):
        return value
    return "unclassified_delivery_error"
