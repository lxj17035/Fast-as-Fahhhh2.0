import unittest
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from backend.errors import AppError
from backend.pdf import PDFService
from backend.quotations import QuotationService
from backend.settings import SettingsService
from backend.store import Store


class PDFTests(unittest.TestCase):
    def setUp(self):
        self.store = Store.for_test()
        self.addCleanup(self.store.close)
        self.quotes = QuotationService(self.store, SettingsService(self.store))
        self.pdfs = PDFService(self.store, self.quotes)
        self.quote = self.quotes.create("fictional-enquiry", issue_date="2026-10-23")

    def priced(self):
        return self.quotes.update(self.quote["id"], {"version": 1, "items": [
            {"description": "Printed T-shirts", "quantity": 20, "unitPrice": "25.00"}]})

    def test_saved_pdf_contains_details_dates_and_exact_total(self):
        self.priced()
        data, version = self.pdfs.get(self.quote["id"], 2)
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertEqual(version, 2)
        reader = PdfReader(BytesIO(data))
        self.assertEqual(len(reader.pages), 1)
        content = reader.pages[0].extract_text()
        for expected in ["Example Print Studio", "Example Events", "Printed T-shirts", "2026-10-23",
                         "2026-11-23", "25.00", "500.00", "MYR", "Page 1"]:
            self.assertIn(expected, content)

    def test_unpriced_draft_is_labelled_without_zero_prices(self):
        data, _ = self.pdfs.get(self.quote["id"])
        content = PdfReader(BytesIO(data)).pages[0].extract_text()
        self.assertIn("INCOMPLETE DRAFT", content)
        self.assertIn("Pending pricing", " ".join(content.split()))

    def test_preview_cache_is_exact_and_stale_versions_rejected(self):
        first, _ = self.pdfs.get(self.quote["id"], 1)
        self.assertEqual(self.pdfs.get(self.quote["id"], 1)[0], first)
        self.priced()
        with self.assertRaises(AppError) as error:
            self.pdfs.get(self.quote["id"], 1)
        self.assertEqual(error.exception.status, 409)
        self.assertNotEqual(self.pdfs.get(self.quote["id"], 2)[0], first)

    def test_multipage_table_repeats_headers_and_keeps_last_item(self):
        items = [{"description": f"Item {i}: fictional print service, " + "extended description " * 20,
                  "quantity": 1, "unitPrice": "2.00"} for i in range(30)]
        self.quotes.update(self.quote["id"], {"version": 1, "items": items, "notes": "Fictional review note"})
        data, _ = self.pdfs.get(self.quote["id"])
        reader = PdfReader(BytesIO(data))
        self.assertGreater(len(reader.pages), 1)
        for page in reader.pages:
            self.assertIn("Description", page.extract_text())
            self.assertEqual(page.extract_text().count("Description"), 1)
        self.assertIn("Item 29:", "\n".join(p.extract_text() for p in reader.pages))
        self.assertIn("60.00", reader.pages[-1].extract_text())
        self.assertIn("Fictional review note", reader.pages[-1].extract_text())

    def test_literal_markup_and_chinese_names(self):
        self.quotes.update(self.quote["id"], {"version": 1, "client": {"name": "测试客户"},
                           "notes": "Use <script>literal & safe</script> text"})
        data, _ = self.pdfs.get(self.quote["id"])
        content = PdfReader(BytesIO(data)).pages[0].extract_text()
        self.assertIn("测试客户", content)
        self.assertIn("<script>literal & safe</script>", content)

    def test_sent_pdf_is_identical_after_company_settings_change(self):
        self.priced()
        before, _ = self.pdfs.get(self.quote["id"], 2)
        self.quotes.begin_send(self.quote["id"], 2, "Demo PM", "pm", today=date(2026, 10, 23))
        self.quotes.record_send_result(self.quote["id"], "accepted", "mock-reference")
        self.quotes.settings.update_settings({"companyName": "Other fictional business"})
        self.assertEqual(self.pdfs.get(self.quote["id"], 2)[0], before)

    def test_very_long_cjk_item_can_split_across_pages(self):
        self.quotes.update(self.quote["id"], {"version": 1, "items": [
            {"description": "测试印刷服务" * 300, "quantity": 1, "unitPrice": "1.00"}]})
        data, _ = self.pdfs.get(self.quote["id"])
        reader = PdfReader(BytesIO(data))
        self.assertGreater(len(reader.pages), 1)
        self.assertIn("1.00", reader.pages[-1].extract_text())
