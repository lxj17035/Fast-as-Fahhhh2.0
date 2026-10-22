import tempfile
import unittest
from pathlib import Path

from backend.errors import AppError
from backend.settings import SettingsService, VALIDITIES
from backend.store import Store


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.service = SettingsService(self.store)

    def test_seed_is_fictional_and_defaults_to_one_month(self):
        self.assertIn("fictional", self.service.get_settings()["companyName"])
        self.assertEqual(self.service.get_settings()["defaultValidity"], "1m")

    def test_update_all_supported_validities(self):
        for validity in VALIDITIES:
            self.assertEqual(self.service.update_settings({"defaultValidity": validity})[
                "defaultValidity"], validity)

    def test_edit_client_name_and_address(self):
        result = self.service.update_client("demo-client", {"name": "  Demo Co  ", "address": ""})
        self.assertEqual(result["name"], "Demo Co")
        self.assertEqual(result["address"], "")

    def test_invalid_settings_do_not_partially_save(self):
        original = self.service.get_settings()
        for patch in [{"currency": "myr"}, {"defaultValidity": "30d"},
                      {"companyName": ""}, {"apiKey": "forbidden"},
                      {"currency": "USD", "defaultValidity": "bad"}]:
            with self.assertRaises(AppError):
                self.service.update_settings(patch)
            self.assertEqual(self.service.get_settings(), original)

    def test_reject_invalid_client_and_unknown_id(self):
        for patch in [{"name": " "}, {"address": None}, {"role": "pm"}]:
            with self.assertRaises(AppError):
                self.service.update_client("demo-client", patch)
        with self.assertRaises(AppError) as error:
            self.service.get_client("missing")
        self.assertEqual(error.exception.status, 404)

    def test_reopen_database_preserves_edits_and_seed_does_not_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.sqlite3"
            first = Store(path)
            service = SettingsService(first)
            service.update_settings({"companyName": "Changed Demo", "currency": "USD"})
            service.update_client("demo-client", {"address": "99 Fictional Road"})
            first.close()
            second = Store(path)
            try:
                reopened = SettingsService(second)
                self.assertEqual(reopened.get_settings()["companyName"], "Changed Demo")
                self.assertEqual(reopened.get_client("demo-client")["address"], "99 Fictional Road")
            finally:
                second.close()


if __name__ == "__main__":
    unittest.main()
