import pytest

from backend.drafting import validate_extraction, EXTRACTION_SCHEMA
from backend.errors import AppError
from backend.quotations import QuotationService
from backend.settings import SettingsService
from backend.store import Store


def output(**extra):
    return {"summary": "Customer requests black shirts for an event", "clientName": None,
            "clientAddress": None, "items": [], "missingInformation": [], **extra}


def test_title_bounds_and_legacy_extractions():
    assert "shortTitle" in EXTRACTION_SCHEMA["required"]
    assert validate_extraction(output(shortTitle="20 black T-shirts"))["shortTitle"] == "20 black T-shirts"
    assert len(validate_extraction(output(shortTitle="一二三四五六七八九十一二三四五六七"))["shortTitle"]) == 15
    assert validate_extraction(output(shortTitle="one two three four five six seven"))["shortTitle"] == "one two three four five six"
    assert "shortTitle" not in validate_extraction(output())
    with pytest.raises(AppError):
        validate_extraction(output(shortTitle=42))


def test_title_is_saved_without_pricing_or_source_authority():
    store = Store.for_test()
    try:
        settings = SettingsService(store)
        quotes = QuotationService(store, settings)
        with store.transaction():
            store.put("enquiries", "title-test", {"id": "title-test", "text": "20 black shirts",
                      "source": "telegram", "chatId": "synthetic", "clientId": "demo-client"})
        quote = quotes.create("title-test", extracted=output(shortTitle="20 black shirts"))
        assert quotes.get(quote["id"])["shortTitle"] == "20 black shirts"
        assert quote["total"] is None
        assert quote["summary"] == "Customer requests black shirts for an event"
    finally:
        store.close()
