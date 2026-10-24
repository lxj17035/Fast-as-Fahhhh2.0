import calendar
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from .errors import AppError, object_fields, text
from .settings import VALIDITIES, require_profile

BUSINESS_TZ = timezone(timedelta(hours=8), "Asia/Kuala_Lumpur")


def business_today():
    return datetime.now(BUSINESS_TZ).date()


def parse_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise AppError("issueDate must be a valid YYYY-MM-DD date") from None


def expiry_date(issue_date, validity):
    issue = parse_date(issue_date)
    if validity not in VALIDITIES:
        raise AppError("Unsupported validity")
    if validity.endswith("d"):
        try:
            return (issue + timedelta(days=int(validity[:-1]))).isoformat()
        except OverflowError:
            raise AppError("Expiry date is outside supported range") from None
    month_index = issue.year * 12 + issue.month - 1 + int(validity[:-1])
    year, month = divmod(month_index, 12)
    if year > 9999:
        raise AppError("Expiry date is outside supported range")
    month += 1
    return date(year, month, min(issue.day, calendar.monthrange(year, month)[1])).isoformat()


def decimal_value(value, field, *, price=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise AppError(f"{field} must be a decimal number")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise AppError(f"{field} must be a decimal number") from None
    maximum = Decimal("1000000000") if price else Decimal("1000000")
    if not amount.is_finite() or amount < 0 or amount > maximum or (not price and amount == 0):
        raise AppError(f"{field} is outside the allowed range")
    places = 2 if price else 3
    if amount != amount.quantize(Decimal(1).scaleb(-places)):
        raise AppError(f"{field} supports at most {places} decimal places")
    return amount


def money(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def normalize_items(items):
    if not isinstance(items, list) or len(items) > 100:
        raise AppError("items must be a list with at most 100 lines")
    result = []
    total = Decimal(0)
    complete = bool(items)
    for index, item in enumerate(items):
        object_fields(item, {"description", "item_name", "quantity", "unitPrice", "unit_price", "unit", "notes"})
        description = text(item.get("item_name", item.get("description", "")), "item_name", limit=2000)
        if "item_name" in item and "description" in item and text(item["description"], "description", limit=2000) != description:
            raise AppError("item_name and legacy description disagree")
        unit = text(item.get("unit", "unit"), "unit", required=True, limit=40)
        notes = text(item.get("notes", ""), "item.notes", limit=2000)
        quantity = item.get("quantity")
        price = item.get("unit_price", item.get("unitPrice"))
        if "unit_price" in item and "unitPrice" in item:
            legacy = item["unitPrice"]
            if (legacy is None) != (price is None) or (price is not None and
                decimal_value(legacy, "unitPrice", price=True) != decimal_value(price, "unit_price", price=True)):
                raise AppError("unit_price and legacy unitPrice disagree")
        quantity = None if quantity is None else decimal_value(quantity, f"items.{index}.quantity")
        price = None if price is None else decimal_value(price, f"items.{index}.unitPrice", price=True)
        line_total = None
        if quantity is not None and price is not None:
            line_total = money(quantity * price)
            total += Decimal(line_total)
        else:
            complete = False
        result.append({"description": description, "item_name": description, "unit": unit, "notes": notes,
                       "quantity": None if quantity is None else format(quantity, "f"),
                       "unitPrice": None if price is None else money(price),
                       "unit_price": None if price is None else money(price), "amount": line_total,
                       "lineTotal": line_total})
    return result, money(total) if complete else None


def expected_version(value, expected):
    if isinstance(expected, bool) or not isinstance(expected, int) or value["version"] != expected:
        raise AppError("Quotation changed; reload and review the current version", 409)


class QuotationService:
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings

    def get(self, quotation_id):
        return self.store.get("quotations", quotation_id)

    def source_ids(self, enquiry_id):
        try:
            return self.store.get("enquiries", enquiry_id).get("messageUpdateIds", [])
        except AppError as error:
            if error.status != 404:
                raise
            return []  # Standalone synthetic service fixtures have no receipt.

    def source_is_current(self, value):
        try:
            enquiry = self.store.get("enquiries", value["enquiryId"])
        except AppError as error:
            if error.status != 404:
                raise
            return True
        legacy = [enquiry["providerUpdateId"]] if enquiry.get("providerUpdateId") else []
        if enquiry.get("unassignedMessageIds"):
            return False
        return value.get("reviewedMessageIds", legacy) == enquiry.get("messageUpdateIds", [])

    def create(self, enquiry_id, client_id="demo-client", *, issue_date=None,
               extracted=None, draft_mode="manual", draft_error=None, source_message_ids=None):
        extracted = extracted or {}
        with self.store.transaction():
            existing = [q for q in self.store.list("quotations") if q["enquiryId"] == enquiry_id]
            if existing:
                return existing[-1]
            try:
                enquiry = self.store.get("enquiries", enquiry_id)
            except AppError as error:
                if error.status != 404:
                    raise
                # Retain the standalone service/fixture contract with no intake row.
                identity = self.settings.active_profile_id()
            else:
                identity = enquiry["business_profile_id"]
            company = self.settings.get_settings(identity)
            client = self.settings.get_client(client_id, identity)
            if extracted.get("clientName"):
                client["name"] = extracted["clientName"]
            if extracted.get("clientAddress"):
                client["address"] = extracted["clientAddress"]
            quote_id = uuid4().hex
            issue = issue_date or business_today().isoformat()
            extracted_items = extracted.get("items", [])
            if not isinstance(extracted_items, list):
                raise AppError("Extracted items must be a list")
            # Pricing authority is enforced here even for an injected/faulty provider.
            unpriced = []
            for item in extracted_items:
                if not isinstance(item, dict):
                    raise AppError("Extracted item must be an object")
                unpriced.append({**{k: v for k, v in item.items() if k not in {"unitPrice", "unit_price"}},
                                 "unit_price": None})
            items, total = normalize_items(unpriced)
            current_source = self.source_ids(enquiry_id)
            reviewed_source = current_source if source_message_ids is None else source_message_ids
            if (not isinstance(reviewed_source, list) or any(not isinstance(i, str) for i in reviewed_source)
                    or len(reviewed_source) != len(set(reviewed_source))
                    or [i for i in current_source if i in reviewed_source] != reviewed_source):
                raise AppError("Draft evidence no longer matches its source conversation", 409)
            value = {
                "id": quote_id, "number": "QUO-" + quote_id[:12].upper(),
                "enquiryId": enquiry_id, "version": 1, "status": "draft",
                "business_profile_id": identity,
                "company": company, "client": client, "currency": company["currency"],
                "issueDate": issue, "validity": company["defaultValidity"],
                "expiryDate": expiry_date(issue, company["defaultValidity"]),
                "items": items, "total": total, "notes": "",
                "summary": extracted.get("summary", ""),
                "missingInformation": extracted.get("missingInformation", []),
                "draftMode": draft_mode, "draftError": draft_error,
                "reviewedMessageIds": reviewed_source,
            }
            self.store.put("quotations", quote_id, value)
            return value

    def update(self, quotation_id, patch, *, role=None):
        object_fields(patch, {"version", "client", "issueDate", "validity", "items", "notes", "missingInformation", "reviewedMessageIds"})
        with self.store.transaction():
            value = self.get(quotation_id)
            expected_version(value, patch.get("version"))
            if value["status"] not in ("draft", "send_failed"):
                raise AppError("Quotation is locked after approval or sending", 409)
            if "client" in patch:
                object_fields(patch["client"], {"name", "address"})
                for key, item in patch["client"].items():
                    value["client"][key] = text(item, "client." + key)
            for key in ("issueDate", "validity"):
                if key in patch:
                    value[key] = patch[key]
            value["expiryDate"] = expiry_date(value["issueDate"], value["validity"])
            if "items" in patch:
                original_items = value["items"]
                supplied = patch["items"]
                if isinstance(supplied, list):
                    # Legacy editors may omit the new descriptive fields.
                    supplied = [{**{k: value["items"][i].get(k, "unit" if k == "unit" else "")
                                    for k in ("unit", "notes") if i < len(value["items"])}, **item}
                                if isinstance(item, dict) else item for i, item in enumerate(supplied)]
                value["items"], value["total"] = normalize_items(supplied)
                prices_changed = any(
                    item["unitPrice"] != (original_items[i]["unitPrice"] if i < len(original_items) else None)
                    for i, item in enumerate(value["items"]))
                if prices_changed and role != "pm":
                    raise AppError("Only the simulated Manager (PM) may change unit prices", 403)
            if "notes" in patch:
                value["notes"] = text(patch["notes"], "notes", limit=4000)
            if "missingInformation" in patch:
                missing = patch["missingInformation"]
                if not isinstance(missing, list) or len(missing) > 50:
                    raise AppError("missingInformation must be a list of up to 50 strings")
                value["missingInformation"] = [text(x, "missingInformation", required=True) for x in missing]
            if "reviewedMessageIds" in patch:
                reviewed = patch["reviewedMessageIds"]
                if not isinstance(reviewed, list) or reviewed != self.source_ids(value["enquiryId"]):
                    raise AppError("Customer conversation changed; reload and review every current message", 409)
                value["reviewedMessageIds"] = reviewed
            value["version"] += 1
            value["status"] = "draft"
            self.store.put("quotations", quotation_id, value)
            return value

    def validate_for_send(self, quotation_id, version, role, *, today=None):
        value = self.get(quotation_id)
        if role != "pm":
            raise AppError("Only the simulated PM role may approve sending", 403)
        expected_version(value, version)
        if value["status"] not in ("draft", "send_failed"):
            raise AppError("Quotation is already approved, sent, or has an uncertain outcome", 409)
        if not self.source_is_current(value):
            raise AppError("New customer messages require Staff review and an updated saved quotation", 409)
        fields = {}
        if not value["client"]["name"].strip():
            fields["client.name"] = "Client name is required"
        if not value["items"]:
            fields["items"] = "At least one item is required"
        for index, item in enumerate(value["items"]):
            for key in ("description", "quantity", "unitPrice"):
                if item[key] is None or item[key] == "":
                    fields[f"items.{index}.{key}"] = "Required before sending"
            if not item.get("unit", "unit").strip():
                fields[f"items.{index}.unit"] = "Required before sending"
        if value["missingInformation"]:
            fields["missingInformation"] = "Resolve or dismiss the missing details before approval"
        if parse_date(value["expiryDate"]) < (today or business_today()):
            fields["expiryDate"] = "Quotation has expired"
        if parse_date(value["issueDate"]) > (today or business_today()):
            fields["issueDate"] = "Quotation issue date is in the future"
        if fields:
            raise AppError("Quotation is not ready to send", fields=fields)
        return value

    def fork(self, quotation_id, patch, actor):
        object_fields(patch, {"version", "relationship", "enquiry_id"})
        if actor not in {"sales", "pm"}:
            raise AppError("Explicit Staff action is required", 403)
        with self.store.transaction():
            original = require_profile(self.get(quotation_id), self.settings.active_profile_id())
            expected_version(original, patch.get("version"))
            if original["status"] != "sent":
                raise AppError("Only a sent quotation can have a revision/additional relationship", 409)
            relationship = patch.get("relationship")
            if not isinstance(relationship, str) or relationship not in {"revision", "additional"}:
                raise AppError("Confirm revision or additional with the customer before creating a quotation")
            target = original["enquiryId"]
            if relationship == "additional":
                target = text(patch.get("enquiry_id"), "enquiry_id", required=True)
                other = require_profile(self.store.get("enquiries", target), original["business_profile_id"])
                source = self.store.get("enquiries", original["enquiryId"])
                if target == original["enquiryId"] or other["chatId"] != source["chatId"]:
                    raise AppError("Additional quotation requires a distinct request in the same customer chat")
                for existing in self.store.list("quotations"):
                    if existing["enquiryId"] == target:
                        if existing.get("parentQuotationId") not in {None, original["id"]}:
                            raise AppError("Additional request already relates to another quotation", 409)
                        if existing["status"] != "draft":
                            raise AppError("Additional quotation is already approved or sent", 409)
                        if existing.get("parentQuotationId") == original["id"] and existing.get("relationship") == "additional":
                            return existing
                        existing.update(parentQuotationId=original["id"], parentQuotationNumber=original["number"],
                                        relationship="additional", version=existing["version"] + 1)
                        self.store.put("quotations", existing["id"], existing)
                        return existing
            else:
                for existing in reversed(self.store.list("quotations")):
                    if existing.get("parentQuotationId") == quotation_id and existing["status"] == "draft":
                        return existing
            value = deepcopy(original)
            identity = uuid4().hex
            issue = business_today().isoformat()
            value.update(id=identity, number="QUO-" + identity[:12].upper(), enquiryId=target,
                         version=1, status="draft", parentQuotationId=quotation_id, relationship=relationship,
                         parentQuotationNumber=original["number"],
                         issueDate=issue, expiryDate=expiry_date(issue, value["validity"]),
                         reviewedMessageIds=[], draftMode="manual", draftError=None,
                         missingInformation=["Review the customer request before preparing this quotation"])
            for key in ("approvedBy", "providerReference", "sendError"):
                value.pop(key, None)
            # Previously approved prices never become implicit approval of a revision.
            value["items"], value["total"] = normalize_items([
                {"item_name": item.get("item_name", item["description"]), "quantity": item["quantity"],
                 "unit": item.get("unit", "unit"), "unit_price": None, "notes": item.get("notes", "")}
                for item in (value["items"] if relationship == "revision" else [])])
            self.store.put("quotations", identity, value)
            return value

    def begin_send(self, quotation_id, version, actor, role, *, today=None):
        """Sweeway calls this atomically before sending the saved PDF version.

        The caller is responsible for ensuring the PM reviewed that version,
        latest messages, the recipient, and persisting its approval/send events.
        """
        with self.store.transaction():
            value = self.validate_for_send(quotation_id, version, role, today=today)
            value["approvedBy"] = text(actor, "actor", required=True)
            value["status"] = "sending"
            self.store.put("quotations", quotation_id, value)
            return value

    def record_send_result(self, quotation_id, outcome, provider_reference=None):
        """Transport integration helper; never performs an external send."""
        if outcome not in ("accepted", "failed", "uncertain"):
            raise AppError("Unsupported send outcome")
        with self.store.transaction():
            value = self.get(quotation_id)
            if value["status"] != "sending":
                raise AppError("No send is in progress", 409)
            value["status"] = {"accepted": "sent", "failed": "send_failed", "uncertain": "send_uncertain"}[outcome]
            value["providerReference"] = provider_reference
            self.store.put("quotations", quotation_id, value)
            return value
