import unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor

from backend.errors import AppError
from backend.quotations import QuotationService, expiry_date
from backend.settings import SettingsService
from backend.store import Store


class QuotationTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.settings = SettingsService(self.store)
        self.service = QuotationService(self.store, self.settings)
        self.quote = self.service.create("demo-enquiry", issue_date="2026-10-23")

    def ready(self, items=None):
        return self.service.update(self.quote["id"], {"version": 1, "items": items or [
            {"description": "Printed shirts", "quantity": "20", "unitPrice": "25.00"}]})

    def test_all_validities_and_month_end_leap_year(self):
        for code, expected in {"7d": "2026-10-30", "14d": "2026-11-06", "1m": "2026-11-23",
                               "2m": "2026-12-23", "3m": "2027-01-23"}.items():
            self.assertEqual(expiry_date("2026-10-23", code), expected)
        self.assertEqual(expiry_date("2027-01-31", "1m"), "2027-02-28")
        self.assertEqual(expiry_date("2028-01-31", "1m"), "2028-02-29")
        self.assertEqual(expiry_date("2026-12-31", "2m"), "2027-02-28")

    def test_invalid_dates_and_validity(self):
        for day, validity in [("2026-02-30", "1m"), ("20261023", "1m"),
                              (None, "1m"), ("2026-10-23", "30d"), ("9999-12-31", "7d")]:
            with self.assertRaises(AppError):
                expiry_date(day, validity)

    def test_exact_totals_and_fractional_quantity_rounding(self):
        value = self.ready([
            {"description": "Shirts", "quantity": 20, "unitPrice": "25.00"},
            {"description": "Material", "quantity": "0.125", "unitPrice": "0.20"},
            {"description": "Small item", "quantity": 3, "unitPrice": "0.10"}])
        self.assertEqual(value["items"][1]["lineTotal"], "0.03")
        self.assertEqual(value["total"], "500.33")

    def test_blank_price_stays_unknown_and_blocks_send(self):
        value = self.ready([{"description": "Shirts", "quantity": 20, "unitPrice": None}])
        self.assertIsNone(value["total"])
        with self.assertRaises(AppError) as error:
            self.service.validate_for_send(value["id"], 2, "pm", today=date(2026, 10, 23))
        self.assertIn("items.0.unitPrice", error.exception.fields)

    def test_zero_price_is_explicit_and_allowed(self):
        value = self.ready([{"description": "Complimentary sample", "quantity": 1, "unitPrice": "0"}])
        self.assertEqual(value["total"], "0.00")
        self.service.validate_for_send(value["id"], 2, "pm", today=date(2026, 10, 23))

    def test_invalid_money_and_quantities_rejected_without_save(self):
        for key, bad in [("unitPrice", "NaN"), ("unitPrice", "Infinity"), ("unitPrice", "-1"),
                         ("unitPrice", "1.005"), ("quantity", 0), ("quantity", True),
                         ("quantity", "0.0001"), ("quantity", {})]:
            item = {"description": "Item", "quantity": 1, "unitPrice": "1.00", key: bad}
            with self.assertRaises(AppError):
                self.service.update(self.quote["id"], {"version": 1, "items": [item]})
        self.assertEqual(self.service.get(self.quote["id"])["version"], 1)

    def test_pm_role_required_and_expiry_inclusive(self):
        value = self.ready()
        with self.assertRaises(AppError) as error:
            self.service.validate_for_send(value["id"], 2, "sales")
        self.assertEqual(error.exception.status, 403)
        self.service.validate_for_send(value["id"], 2, "pm", today=date(2026, 11, 23))
        with self.assertRaises(AppError):
            self.service.validate_for_send(value["id"], 2, "pm", today=date(2026, 11, 24))

    def test_stale_version_and_invalid_patch(self):
        self.ready()
        for patch in [{"version": 1, "notes": "stale"}, {"version": 2, "total": "0"}]:
            with self.assertRaises(AppError):
                self.service.update(self.quote["id"], patch)

    def test_sent_snapshot_preserved_and_default_changes_only_new_drafts(self):
        value = self.ready()
        self.service.begin_send(value["id"], 2, "Demo PM", "pm", today=date(2026, 10, 23))
        self.service.record_send_result(value["id"], "accepted", "test-provider-ref")
        self.settings.update_settings({"companyName": "Other Demo", "defaultValidity": "7d"})
        self.settings.update_client("demo-client", {"name": "New Name"})
        sent = self.service.get(value["id"])
        self.assertEqual(sent["company"]["companyName"], self.quote["company"]["companyName"])
        self.assertEqual(sent["client"]["name"], self.quote["client"]["name"])
        self.assertEqual(sent["validity"], "1m")
        with self.assertRaises(AppError):
            self.service.update(sent["id"], {"version": 2, "notes": "overwrite"})
        self.assertEqual(self.service.create("new-enquiry")["validity"], "7d")

    def test_repeat_creation_does_not_overwrite_pm_work(self):
        self.ready()
        result = self.service.create("demo-enquiry", extracted={"summary": "replacement"})
        self.assertEqual(result["id"], self.quote["id"])
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["total"], "500.00")

    def test_concurrent_approvals_only_one_can_begin(self):
        self.ready()
        def approve(_):
            try:
                self.service.begin_send(self.quote["id"], 2, "Demo PM", "pm", today=date(2026, 10, 23))
                return True
            except AppError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(approve, range(2))), 1)

    def test_unknown_delivery_blocks_retry_but_known_failure_allows_it(self):
        value = self.ready()
        args = (value["id"], 2, "Demo PM", "pm")
        self.service.begin_send(*args, today=date(2026, 10, 23))
        self.service.record_send_result(value["id"], "failed")
        self.service.begin_send(*args, today=date(2026, 10, 23))
        self.service.record_send_result(value["id"], "uncertain")
        with self.assertRaises(AppError):
            self.service.begin_send(*args, today=date(2026, 10, 23))


if __name__ == "__main__":
    unittest.main()
