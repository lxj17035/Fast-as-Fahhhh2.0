"""One final Manager review from the exact saved quotation and PDF version."""
from hashlib import sha256

from backend.errors import AppError
from backend.pdf import PDFService
from backend.settings import require_profile


def telegram_summary(quote):
    items = []
    for item in quote["items"][:3]:
        name = item.get("item_name", item["description"]).replace("\n", " ")
        items.append(f'{item["quantity"]} {item.get("unit", "unit")} {name[:80]}')
    extra = f' (+{len(quote["items"]) - 3} more; see PDF)' if len(quote["items"]) > 3 else ""
    currency = "RM" if quote["currency"] == "MYR" else quote["currency"]
    return (f'Quotation {quote["number"]} (v{quote["version"]})\n'
            f'Items: {"; ".join(items)}{extra}\n'
            f'Total: {currency} {quote["total"]}\n'
            f'Issued: {quote["issueDate"]}\nValid until: {quote["expiryDate"]}\n'
            'Please review the attached PDF and reply before the expiry date.')


class ReviewService:
    def __init__(self, quotations):
        self.quotations, self.store = quotations, quotations.store

    def get(self, quotation_id, version, role):
        if role != "pm":
            raise AppError("Manager (PM) review is required", 403)
        with self.store.transaction():
            quote = require_profile(self.quotations.get(quotation_id), self.quotations.settings.active_profile_id())
            resume = quote["status"] == "send_failed" and self.quotations.delivered_pdf(quotation_id)
            quote = self.quotations.validate_for_send(quotation_id, version, role, delivered_pdf_retry=resume)
            enquiry = self.store.get("enquiries", quote["enquiryId"])
            if enquiry["source"] != "telegram":
                raise AppError("Synthetic intake has no Telegram delivery target", 422)
            pdf, saved_version = PDFService(self.store, self.quotations).get(quotation_id, version)
            configured = self.quotations.settings.get_profile(quote["business_profile_id"])
            profile = {"id": configured["id"], "industry": configured["industry"], **quote["company"]}
            return {"quotation": quote, "business_profile": profile,
                    "pdf": {"url": f"/api/quotations/{quotation_id}/pdf?version={saved_version}",
                            "version": saved_version, "sha256": sha256(pdf).hexdigest(), "content_type": "application/pdf"},
                    "telegram_summary": telegram_summary(quote),
                    "source_message_ids": quote["reviewedMessageIds"] if resume else self.quotations.source_ids(quote["enquiryId"]),
                    "delivery_mode": "summary_only" if resume else "pdf_and_summary", "send_ready": True}
