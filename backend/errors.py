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
