"""Append-only application activity, with stable keys for retried operations."""
from datetime import datetime, timezone

from .errors import AppError


def record_activity(store, key, **fields):
    with store.transaction():
        try:
            return store.get("activity", key)
        except AppError as error:
            if error.status != 404:
                raise
        event = {"id": key, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
        store.put("activity", key, event)
        return event


def enquiry_activity(store, enquiry_id):
    store.get("enquiries", enquiry_id)
    return sorted((event for event in store.list("activity") if event["enquiryId"] == enquiry_id),
                  key=lambda event: (event["timestamp"], event["id"]))
