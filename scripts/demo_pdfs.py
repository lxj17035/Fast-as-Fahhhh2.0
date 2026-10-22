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
    finally:
        store.close()


if __name__ == "__main__":
    main()
