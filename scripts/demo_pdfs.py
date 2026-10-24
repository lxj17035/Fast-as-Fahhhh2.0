"""Generate fictional PDF fixtures for visual review without any network calls."""
from pathlib import Path

from backend.pdf import PDFService
from backend.quotations import QuotationService
from backend.settings import SettingsService
from backend.store import Store


def main():
    output = Path("output/pdf")
    output.mkdir(parents=True, exist_ok=True)
    store = Store.for_test()
    try:
        settings = SettingsService(store)
        quotes = QuotationService(store, settings)
        pdfs = PDFService(store, quotes)
        for name, count in [("quotation-sample", 1), ("quotation-multipage", 30)]:
            quote = quotes.create(name, issue_date="2026-10-23")
            items = [{"description": "Printed event T-shirts", "quantity": 20, "unitPrice": "25.00"}]
            if count > 1:
                items = [{"description": f"Service {i + 1}: " + "Fictional print production and artwork preparation. " * 8,
                          "quantity": 1, "unitPrice": "25.00"} for i in range(count)]
            quotes.update(quote["id"], {"version": 1,
                          "client": {"name": "Example Events / 测试客户", "address": "12 Demo Road, Fictional Town"},
                          "items": items,
                          "notes": "Please review item details before approval. This document uses fictional data only."})
            path = output / (name + ".pdf")
            path.write_bytes(pdfs.get(quote["id"], 2)[0])
            print(path.resolve())
        for identity, item in [
            ("printing", {"item_name": "Event flyers", "quantity": 1000, "unit": "pcs",
                          "unit_price": "0.25", "notes": "A5, full colour, 150gsm. Fictional sample."}),
            ("cleaning", {"item_name": "Office cleaning", "quantity": 2, "unit": "visit",
                          "unit_price": "150.00", "notes": "800 sq ft office; windows included. Fictional sample."}),
            ("repair", {"item_name": "Laptop diagnosis", "quantity": "1.5", "unit": "hour",
                        "unit_price": "80.00", "notes": "Fictional device with screen fault; diagnosis only."}),
        ]:
            settings.select_profile({"business_profile_id": identity})
            quote = quotes.create("sample-" + identity, settings.demo_client_id(identity), issue_date="2026-10-23")
            saved = quotes.update(quote["id"], {"version": 1, "items": [item],
                                               "notes": "Synthetic-data demonstration. No customer delivery."})
            path = output / ("quotation-" + identity + ".pdf")
            path.write_bytes(pdfs.get(saved["id"], saved["version"])[0])
            print(path.resolve())
    finally:
        store.close()


if __name__ == "__main__":
    main()
