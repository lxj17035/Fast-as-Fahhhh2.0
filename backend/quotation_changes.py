"""Small version-bound suggestion sets; only explicit Staff apply mutates a draft."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from backend.errors import AppError, object_fields
from backend.quotations import expected_version, normalize_items
from backend.settings import require_profile

ITEM_FIELDS = {"item_name", "description", "quantity", "unit", "notes"}
QUOTE_FIELDS = {"client.name", "client.address", "issueDate", "validity", "notes"}


def validate_change(change):
    object_fields(change, {"type", "index", "field", "value", "data"})
    kind = change.get("type")
    if not isinstance(kind, str):
        raise AppError("Suggestion type must be text")
    if kind in {"ADD_ITEM", "UPDATE_ITEM"}:
        data = change.get("data")
        object_fields(data, ITEM_FIELDS)
        if not data:
            raise AppError("Suggested item changes must contain fields")
        if kind == "UPDATE_ITEM" and (type(change.get("index")) is not int or change["index"] < 0):
            raise AppError("UPDATE_ITEM requires a nonnegative item index")
        # Existing validation rejects invalid quantities/units; suggestions never carry prices.
        normalize_items([data])
    elif kind == "UPDATE_FIELD":
        if not isinstance(change.get("field"), str) or change["field"] not in QUOTE_FIELDS or "value" not in change:
            raise AppError("Suggested field is not editable")
    else:
        raise AppError("Unsupported suggestion type")
    return deepcopy(change)


def editable_items(items):
    return [{"item_name": item.get("item_name", item["description"]), "quantity": item["quantity"],
             "unit": item.get("unit", "unit"), "unit_price": item["unitPrice"],
             "notes": item.get("notes", "")} for item in items]


class QuotationChanges:
    def __init__(self, quotations):
        self.quotations, self.store = quotations, quotations.store

    def suggest(self, quotation_id, changes, source_message_ids=None):
        if not isinstance(changes, list) or not 1 <= len(changes) <= 100:
            raise AppError("Provide one to 100 suggested changes")
        with self.store.transaction():
            quote = self.quotations.get(quotation_id)
            current_ids = self.quotations.source_ids(quote["enquiryId"])
            evidence = current_ids if source_message_ids is None else source_message_ids
            if not isinstance(evidence, list) or any(i not in current_ids for i in evidence):
                raise AppError("Suggestion evidence must belong to this enquiry")
            suggestions = [{"id": uuid4().hex, **validate_change(change)} for change in changes]
            result = {"id": uuid4().hex, "quotationId": quotation_id,
                      "business_profile_id": quote["business_profile_id"], "baseVersion": quote["version"],
                      "sourceMessageIds": evidence, "conversationMessageIds": current_ids,
                      "changes": suggestions, "applied": False}
            self.store.put("quotation_suggestions", result["id"], result)
            return result

    def list(self, quotation_id):
        return {"items": [s for s in self.store.list("quotation_suggestions") if s["quotationId"] == quotation_id]}

    def apply(self, quotation_id, patch, actor):
        if actor not in {"sales", "pm"}:
            raise AppError("Staff must explicitly apply suggestions", 403)
        object_fields(patch, {"version", "suggestion_set_id", "selected", "edits"})
        with self.store.transaction():
            quote = require_profile(self.quotations.get(quotation_id), self.quotations.settings.active_profile_id())
            expected_version(quote, patch.get("version"))
            proposal_id = patch.get("suggestion_set_id")
            if not isinstance(proposal_id, str) or not proposal_id:
                raise AppError("A suggestion_set_id is required")
            proposal = require_profile(self.store.get("quotation_suggestions", proposal_id),
                                       quote["business_profile_id"])
            if proposal["quotationId"] != quotation_id:
                raise AppError("Suggestions belong to another quotation", 404)
            if proposal["applied"] or proposal["baseVersion"] != quote["version"]:
                raise AppError("Suggestions are stale; review a fresh analysis", 409)
            if proposal["conversationMessageIds"] != self.quotations.source_ids(quote["enquiryId"]):
                raise AppError("Customer conversation changed; request fresh suggestions", 409)
            selected = patch.get("selected")
            if not isinstance(selected, list) or not selected or any(not isinstance(s, str) for s in selected):
                raise AppError("Choose at least one suggested change")
            changes = {c["id"]: c for c in proposal["changes"]}
            if len(selected) != len(set(selected)) or any(s not in changes for s in selected):
                raise AppError("Selected suggestion is unavailable")
            edits = patch.get("edits", {})
            if not isinstance(edits, dict) or set(edits) - set(selected):
                raise AppError("Edits must refer to selected suggestions")
            update = {"version": quote["version"], "reviewedMessageIds": proposal["conversationMessageIds"]}
            items = editable_items(quote["items"])
            applied = []
            for selected_id in selected:
                original = {k: v for k, v in changes[selected_id].items() if k != "id"}
                change = validate_change(edits.get(selected_id, original))
                if change["type"] in {"ADD_ITEM", "UPDATE_ITEM"}:
                    data = deepcopy(change["data"])
                    if "description" in data:
                        data["item_name"] = data.pop("description")
                    if change["type"] == "ADD_ITEM":
                        items.append(data)
                    else:
                        if change["index"] >= len(items):
                            raise AppError("Suggested item no longer exists", 409)
                        items[change["index"]].update(data)
                    update["items"] = items
                elif change["field"].startswith("client."):
                    update.setdefault("client", {})[change["field"].split(".")[1]] = change["value"]
                else:
                    update[change["field"]] = change["value"]
                applied.append({"id": selected_id, **change})
            saved = self.quotations.update(quotation_id, update, role=actor)
            proposal.update(applied=True, appliedBy=actor, appliedVersion=saved["version"],
                            appliedChanges=applied, appliedAt=datetime.now(timezone.utc).isoformat())
            self.store.put("quotation_suggestions", proposal["id"], proposal)
            return saved
