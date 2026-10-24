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
PROFILE_NAMES = {"printing": "Printing", "cleaning": "Cleaning", "repair": "Repair"}
SETTINGS_FIELDS = {"companyName", "companyAddress", "currency", "defaultValidity", "timezone"}


def profile_id(value):
    if not isinstance(value, str) or value not in PROFILE_NAMES:
        raise AppError("Unknown business profile", 422)
    return value


def require_profile(value, expected):
    if value.get("business_profile_id", "printing") != expected:
        raise AppError("Record not found in this business profile", 404)
    return value


class SettingsService:
    def __init__(self, store):
        self.store = store
        with store.transaction():
            if not any(item for item in store.list("settings") if "companyName" in item):
                store.put("settings", "business", SETTINGS)
            existing = {item["id"] for item in store.list("business_profiles")}
            for identity, name in PROFILE_NAMES.items():
                if identity not in existing:
                    company = (store.get("settings", "business") if identity == "printing" else
                               {**SETTINGS, "companyName": f"Example {name} Studio (fictional)"})
                    store.put("business_profiles", identity, {
                        **company, "id": identity, "industry": name,
                    })
                client_id = self.demo_client_id(identity)
                try:
                    store.get("clients", client_id)
                except AppError as error:
                    if error.status != 404:
                        raise
                    store.put("clients", client_id, {
                        **DEMO_CLIENT, "id": client_id, "business_profile_id": identity,
                    })
            try:
                store.get("settings", "active_profile")
            except AppError as error:
                if error.status != 404:
                    raise
                store.put("settings", "active_profile", {"business_profile_id": "printing"})

    @staticmethod
    def demo_client_id(identity):
        return "demo-client" if identity == "printing" else "demo-client-" + identity

    def active_profile_id(self):
        return profile_id(self.store.get("settings", "active_profile")["business_profile_id"])

    def get_profile(self, identity):
        return self.store.get("business_profiles", profile_id(identity))

    def list_profiles(self):
        return {"active_business_profile_id": self.active_profile_id(),
                "items": [self.get_profile(identity) for identity in PROFILE_NAMES]}

    def select_profile(self, patch):
        object_fields(patch, {"business_profile_id"})
        with self.store.transaction():
            identity = profile_id(patch.get("business_profile_id"))
            self.get_profile(identity)
            value = {"business_profile_id": identity}
            self.store.put("settings", "active_profile", value)
            return value

    def get_settings(self, identity=None):
        identity = self.active_profile_id() if identity is None else profile_id(identity)
        company = self.get_profile(identity)
        return {**{key: company[key] for key in SETTINGS_FIELDS}, "business_profile_id": identity}

    def update_settings(self, patch, identity=None):
        object_fields(patch, {"companyName", "companyAddress", "currency", "defaultValidity"})
        with self.store.transaction():
            identity = self.active_profile_id() if identity is None else profile_id(identity)
            value = self.get_profile(identity)
            for key, item in patch.items():
                value[key] = text(item, key, required=key != "companyAddress")
            if value["defaultValidity"] not in VALIDITIES:
                raise AppError("Unsupported defaultValidity")
            if not re.fullmatch(r"[A-Z]{3}", value["currency"]):
                raise AppError("currency must be a three-letter uppercase code")
            self.store.put("business_profiles", identity, value)
            return self.get_settings(identity)

    def get_client(self, client_id, identity=None):
        identity = self.active_profile_id() if identity is None else profile_id(identity)
        return require_profile(self.store.get("clients", client_id), identity)

    def update_client(self, client_id, patch):
        object_fields(patch, {"name", "address"})
        with self.store.transaction():
            value = self.get_client(client_id)
            for key, item in patch.items():
                value[key] = text(item, key, required=key == "name")
            self.store.put("clients", client_id, value)
            return value
