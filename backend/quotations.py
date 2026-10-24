import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from .errors import AppError, object_fields, text
from .settings import VALIDITIES

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
        object_fields(item, {"description", "quantity", "unitPrice"})
        description = text(item.get("description", ""), "description", limit=2000)
        quantity = item.get("quantity")
        price = item.get("unitPrice")
        quantity = None if quantity is None else decimal_value(quantity, f"items.{index}.quantity")
        price = None if price is None else decimal_value(price, f"items.{index}.unitPrice", price=True)
        line_total = None
        if quantity is not None and price is not None:
            line_total = money(quantity * price)
            total += Decimal(line_total)
        else:
            complete = False
        result.append({"description": description,
                       "quantity": None if quantity is None else format(quantity, "f"),
                       "unitPrice": None if price is None else money(price),
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

    def create(self, enquiry_id, client_id="demo-client", *, issue_date=None,
               extracted=None, draft_mode="manual", draft_error=None):
        extracted = extracted or {}
        with self.store.transaction():
            existing = [q for q in self.store.list("quotations") if q["enquiryId"] == enquiry_id]
            if existing:
                return existing[0]
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
            items, total = normalize_items(extracted.get("items", []))
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
            }
            self.store.put("quotations", quote_id, value)
            return value

    def update(self, quotation_id, patch):
        object_fields(patch, {"version", "client", "issueDate", "validity", "items", "notes", "missingInformation"})
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
                value["items"], value["total"] = normalize_items(patch["items"])
            if "notes" in patch:
                value["notes"] = text(patch["notes"], "notes", limit=4000)
            if "missingInformation" in patch:
                missing = patch["missingInformation"]
                if not isinstance(missing, list) or len(missing) > 50:
                    raise AppError("missingInformation must be a list of up to 50 strings")
                value["missingInformation"] = [text(x, "missingInformation", required=True) for x in missing]
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
        fields = {}
        if not value["client"]["name"].strip():
            fields["client.name"] = "Client name is required"
        if not value["items"]:
            fields["items"] = "At least one item is required"
        for index, item in enumerate(value["items"]):
            for key in ("description", "quantity", "unitPrice"):
                if item[key] is None or item[key] == "":
                    fields[f"items.{index}.{key}"] = "Required before sending"
        if value["missingInformation"]:
            fields["missingInformation"] = "Resolve or dismiss the missing details before approval"
        if parse_date(value["expiryDate"]) < (today or business_today()):
            fields["expiryDate"] = "Quotation has expired"
        if fields:
            raise AppError("Quotation is not ready to send", fields=fields)
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
