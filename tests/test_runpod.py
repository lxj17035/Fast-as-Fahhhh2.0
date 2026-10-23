"""No live credentials or network calls; test the Runpod boundary and budget."""
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import Mock

import httpx
import pytest

from backend.drafting import DraftService, ProviderError, configured_extractor
from backend.runpod import RunpodExtractor, DEFAULT_BASE_URL
from backend.settings import SettingsService
from backend.quotations import QuotationService
from backend.store import Store
from scripts.check_live_config import configuration_status

EXTRACTED = {"summary": "Fictional customer requests 20 shirts", "clientName": None,
    "clientAddress": None, "items": [{"description": "Printed shirts", "quantity": 20}],
    "missingInformation": ["Confirm client name"]}


def completion(value=None, finish="stop", **fields):
    return {"choices": [{"finish_reason": finish, "message": {"role": "assistant",
        "content": json.dumps(EXTRACTED if value is None else value), **fields}}]}


@pytest.fixture
def store(tmp_path):
    result = Store.for_test(tmp_path / "ai.sqlite")
    yield result
    result.close()


def test_runpod_payload_uses_low_reasoning_bounded_output_and_no_prices(store):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=completion())
    extractor = RunpodExtractor("synthetic-private-key", store=store, values={},
                                transport=httpx.MockTransport(handle))
    result = extractor.extract("Fictional message", {"company": "Fictional printer"})
    [request] = requests
    assert str(request.url) == DEFAULT_BASE_URL + "/chat/completions"
    assert request.headers["authorization"] == "Bearer synthetic-private-key"
    payload = json.loads(request.content)
    assert payload["reasoning_effort"] == "low" and payload["max_tokens"] == 1024
    assert payload["model"] == "glm-5.3"
    assert set(payload) == {"model", "messages", "reasoning_effort", "max_tokens"}
    assert json.loads(payload["messages"][1]["content"])["message"] == "Fictional message"
    assert request.extensions["timeout"]["read"] == 60
    assert result["clientName"] is None and result["items"][0]["unitPrice"] is None
    usage = store.list("ai_usage")
    assert usage[0]["requests"] == 1
    assert "synthetic-private-key" not in json.dumps(usage)


@pytest.mark.parametrize("status", [302, 400, 401, 429, 500])
def test_http_failures_are_sanitized_and_never_retried(store, status):
    handle = Mock(return_value=httpx.Response(status, text="synthetic-private-provider-data"))
    extractor = RunpodExtractor("synthetic", store=store, values={}, transport=httpx.MockTransport(handle))
    with pytest.raises(ProviderError) as error:
        extractor.extract("Fictional message", {})
    assert "synthetic-private" not in str(error.value)
    assert handle.call_count == 1 and store.list("ai_usage")[0]["requests"] == 1


def test_timeout_does_not_retry_or_expose_raw_errors(store):
    handle = Mock(side_effect=httpx.ReadTimeout("synthetic-private-provider-data"))
    extractor = RunpodExtractor("synthetic", store=store, values={}, transport=httpx.MockTransport(handle))
    with pytest.raises(ProviderError) as error:
        extractor.extract("Fictional", {})
    assert "synthetic-private" not in str(error.value) and handle.call_count == 1


@pytest.mark.parametrize("mode", ["length", "refusal", "tools", "missing", "price", "recipient", "quantity", "invalid_json", "oversized"])
def test_truncated_or_out_of_contract_outputs_are_not_used(store, mode):
    value = deepcopy(EXTRACTED)
    response = completion()
    if mode == "length": response = completion(finish="length")
    if mode == "refusal": response = completion(refusal="synthetic-private-refusal")
    if mode == "tools": response = completion(tool_calls=[{"id": "synthetic-tool"}])
    if mode == "missing": response = {}
    if mode == "price":
        value["items"][0]["unitPrice"] = 10
        response = completion(value)
    if mode == "recipient":
        value["recipient"] = "123456"
        response = completion(value)
    if mode == "quantity":
        value["items"][0]["quantity"] = -1
        response = completion(value)
    handle = Mock(return_value=httpx.Response(200, content=(
        b"not json" if mode == "invalid_json" else b"x" * 65537 if mode == "oversized" else json.dumps(response).encode())))
    with pytest.raises(ProviderError):
        RunpodExtractor("synthetic", store=store, values={}, transport=httpx.MockTransport(handle)).extract("Fictional", {})
    assert handle.call_count == 1


@pytest.mark.parametrize("values", [{"RUNPOD_MAX_TOKENS": "999999"}, {"RUNPOD_MAX_TOKENS": "invalid"},
    {"RUNPOD_DAILY_REQUEST_LIMIT": "0"}, {"RUNPOD_MODEL": ""},
    {"RUNPOD_API_BASE_URL": "https://example.com/openai/v1"}])
def test_invalid_configuration_never_sends_keys_to_another_host(store, values):
    handle = Mock()
    with pytest.raises(ProviderError):
        RunpodExtractor("synthetic", store=store, values=values, transport=httpx.MockTransport(handle)).extract("Fictional", {})
    handle.assert_not_called()
    assert store.list("ai_usage") == []


def test_missing_key_and_oversized_input_never_consume_budget(store):
    handle = Mock()
    for key, message in [("", "Fictional"), ("synthetic", "x" * 16001)]:
        with pytest.raises(ProviderError):
            RunpodExtractor(key, store=store, values={}, transport=httpx.MockTransport(handle)).extract(message, {})
    assert store.list("ai_usage") == []
    handle.assert_not_called()


def test_daily_limit_is_shared_and_does_not_call_the_provider_again(engine):
    stores = [Store(engine=engine), Store(engine=engine)]
    barrier = Barrier(4)
    handle = Mock(return_value=httpx.Response(200, json=completion()))
    def request(index):
        barrier.wait(timeout=10)
        try:
            return RunpodExtractor("synthetic", store=stores[index % 2],
                values={"RUNPOD_DAILY_REQUEST_LIMIT": "1"}, transport=httpx.MockTransport(handle)).extract("Fictional", {})
        except ProviderError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(request, range(4)))
    assert sum(r is not None for r in results) == 1
    assert handle.call_count == 1 and stores[0].list("ai_usage")[0]["requests"] == 1


def test_failure_creates_manual_draft_and_existing_draft_does_not_spend_again(store):
    settings = SettingsService(store)
    with store.transaction():
        store.put("enquiries", "demo", {"id": "demo", "text": "Fictional shirts", "clientId": "demo-client", "source": "demo"})
    handle = Mock(return_value=httpx.Response(429, text="synthetic-private"))
    service = DraftService(store, settings, QuotationService(store, settings),
        RunpodExtractor("synthetic", store=store, values={}, transport=httpx.MockTransport(handle)))
    first = service.create("demo")
    assert first["draftMode"] == "manual" and first["draftError"]
    assert service.create("demo") == first
    assert handle.call_count == 1


def test_factory_selects_runpod_without_falling_back_to_openai(store, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "runpod")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-other-provider-key")
    selected = configured_extractor(store)
    assert isinstance(selected, RunpodExtractor)
    with pytest.raises(ProviderError): selected.extract("Fictional", {})
    assert store.list("ai_usage") == []


def test_readiness_uses_selected_provider_and_never_prints_keys():
    values = {"AI_PROVIDER": "runpod", "RUNPOD_API_KEY": "synthetic-private-key"}
    result = configuration_status(values)
    assert result["readyForAI"] is True and not result["readyForLiveTest"]
    assert "OPENAI_API_KEY" not in result["checks"]
    assert "synthetic-private-key" not in json.dumps(result)
    values["RUNPOD_MAX_TOKENS"] = "999999"
    assert not configuration_status(values)["readyForAI"]


def test_inbound_webhook_uses_runpod_once_and_quota_exhaustion_preserves_manual_draft(engine, settings, headers, update, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv("AI_PROVIDER", "runpod")
    monkeypatch.setenv("RUNPOD_API_KEY", "synthetic-private-key")
    monkeypatch.setenv("RUNPOD_DAILY_REQUEST_LIMIT", "1")
    handle = Mock(side_effect=lambda request: httpx.Response(200, json=completion()))
    monkeypatch.setattr("backend.runpod.httpx.HTTPTransport", lambda **kwargs: httpx.MockTransport(handle))
    with TestClient(create_app(settings, engine)) as client:
        assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
        first = client.get("/api/enquiries").json()["items"][0]
        quote = client.get(f"/api/enquiries/{first['id']}/quotation").json()
        assert quote["draftMode"] == "ai" and quote["items"][0]["unitPrice"] is None
        assert client.post("/api/webhooks/telegram", headers=headers, json=update).json()["status"] == "duplicate"
        assert client.post(f"/api/enquiries/{first['id']}/draft", json={"manual": False}).json()["id"] == quote["id"]
        other = deepcopy(update)
        other["update_id"] += 1
        other["message"]["text"] = "Another fictional enquiry"
        assert client.post("/api/webhooks/telegram", headers=headers, json=other).status_code == 200
        second = next(row for row in client.get("/api/enquiries").json()["items"] if row["id"] != first["id"])
        fallback = client.get(f"/api/enquiries/{second['id']}/quotation").json()
        assert fallback["draftMode"] == "manual" and "Daily AI request limit" in fallback["draftError"]
        assert handle.call_count == 1
