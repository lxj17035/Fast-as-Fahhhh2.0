import re

from .errors import AppError, object_fields, text

VALIDITIES = ("7d", "14d", "1m", "2m", "3m")
SETTINGS = {
    "companyName": "Example Print Studio (fictional)",
    "companyAddress": "1 Demo Street, Fictional Town",
    "currency": "MYR",
    "defaultValidity": "1m",
    "timezone": "Asia/Kuala_Lumpur",
}
DEMO_CLIENT = {
    "id": "demo-client", "name": "Example Events (fictional)",
    "address": "12 Demo Road, Fictional Town",
}


class SettingsService:
    def __init__(self, store):
        self.store = store
        with store.transaction():
            if not store.list("settings"):
                store.put("settings", "business", SETTINGS)
            if not store.list("clients"):
                store.put("clients", DEMO_CLIENT["id"], DEMO_CLIENT)

    def get_settings(self):
        return self.store.get("settings", "business")

    def update_settings(self, patch):
        object_fields(patch, {"companyName", "companyAddress", "currency", "defaultValidity"})
        with self.store.transaction():
            value = self.get_settings()
            for key, item in patch.items():
                value[key] = text(item, key, required=key != "companyAddress")
            if value["defaultValidity"] not in VALIDITIES:
                raise AppError("Unsupported defaultValidity")
            if not re.fullmatch(r"[A-Z]{3}", value["currency"]):
                raise AppError("currency must be a three-letter uppercase code")
            self.store.put("settings", "business", value)
            return value

    def get_client(self, client_id):
        return self.store.get("clients", client_id)

    def update_client(self, client_id, patch):
        object_fields(patch, {"name", "address"})
        with self.store.transaction():
            value = self.get_client(client_id)
            for key, item in patch.items():
                value[key] = text(item, key, required=key == "name")
            self.store.put("clients", client_id, value)
            return value
