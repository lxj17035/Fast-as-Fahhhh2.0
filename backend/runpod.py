"""Runpod public Chat Completions extraction with bounded, one-shot requests."""
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from .drafting import EXTRACTION_SCHEMA, INSTRUCTIONS, ProviderError, validate_extraction
from .errors import AppError

DEFAULT_BASE_URL = "https://api.runpod.ai/v2/b1dd8hy2hqo1nb/openai/v1"
MAX_PROMPT_BYTES = 16000


def configuration(values):
    base_url = values.get("RUNPOD_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = values.get("RUNPOD_MODEL", "glm-5.3").strip()
    if not re.fullmatch(r"https://api\.runpod\.ai/v2/[A-Za-z0-9_-]+/openai/v1", base_url):
        raise ValueError("Invalid Runpod public endpoint")
    if not model or len(model) > 100:
        raise ValueError("Invalid Runpod model")
    try:
        tokens = int(values.get("RUNPOD_MAX_TOKENS", "1024"))
        daily = int(values.get("RUNPOD_DAILY_REQUEST_LIMIT", "100"))
    except (TypeError, ValueError):
        raise ValueError("Invalid Runpod limits") from None
    if not 256 <= tokens <= 2048 or not 1 <= daily <= 1000:
        raise ValueError("Invalid Runpod limits")
    return base_url, model, tokens, daily


class RunpodExtractor:
    def __init__(self, api_key=None, *, store=None, transport=None, values=None):
        self.values = dict(os.environ if values is None else values)
        self.api_key = self.values.get("RUNPOD_API_KEY", "") if api_key is None else api_key
        self.store = store
        self.transport = transport

    def _reserve_request(self, limit):
        if self.store is None:
            raise ProviderError("AI request budget storage is unavailable; review manually")
        day = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date().isoformat()
        key = "runpod:" + day
        with self.store.transaction():
            try:
                usage = self.store.get("ai_usage", key)
            except AppError as error:
                if error.status != 404:
                    raise
                usage = {"date": day, "requests": 0}
            if usage["requests"] >= limit:
                raise ProviderError("Daily AI request limit reached; review manually")
            self.store.put("ai_usage", key, {**usage, "requests": usage["requests"] + 1})

    def extract(self, message, context):
        if not self.api_key.strip():
            raise ProviderError("Runpod API key is not configured; review manually")
        try:
            base_url, model, tokens, daily = configuration(self.values)
        except ValueError:
            raise ProviderError("Runpod configuration is invalid; review manually") from None
        messages = [
            {"role": "system", "content": INSTRUCTIONS +
             " Return one JSON object only, without markdown or reasoning. JSON schema: " +
             json.dumps(EXTRACTION_SCHEMA, ensure_ascii=False)},
            {"role": "user", "content": json.dumps(
                {"message": message, "businessContext": context}, ensure_ascii=False)},
        ]
        if len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) > MAX_PROMPT_BYTES:
            raise ProviderError("Enquiry/context exceeds the AI input limit; review manually")
        self._reserve_request(daily)
        payload = {"model": model, "messages": messages, "max_tokens": tokens,
                   "reasoning_effort": "low"}
        request = httpx.Request("POST", base_url + "/chat/completions",
            headers={"Authorization": "Bearer " + self.api_key}, json=payload,
            extensions={"timeout": {"connect": 10, "read": 60, "write": 10, "pool": 10}})
        transport = self.transport
        owns_transport = transport is None
        if owns_transport:
            transport = httpx.HTTPTransport(retries=0, trust_env=False)
        try:
            response = transport.handle_request(request)
            try:
                if response.status_code != 200:
                    raise ProviderError("Runpod request was unsuccessful; review manually")
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > 65536:
                        raise ProviderError("AI response exceeded the size limit; review manually")
                    body.extend(chunk)
                result = json.loads(body)
            finally:
                response.close()
            choice = result["choices"][0]
            answer = choice["message"]
            if choice.get("finish_reason") != "stop" or answer.get("refusal") or answer.get("tool_calls"):
                raise ProviderError("AI did not complete a quotation draft; review manually")
            if answer.get("role") != "assistant" or not isinstance(answer.get("content"), str):
                raise ProviderError("AI returned an invalid draft; review manually")
            return validate_extraction(json.loads(answer["content"]))
        except ProviderError:
            raise
        except (httpx.HTTPError, OSError):
            raise ProviderError("Runpod service is unavailable; review manually") from None
        except (ValueError, KeyError, TypeError, AttributeError, IndexError, AppError):
            raise ProviderError("AI returned an invalid draft; review manually") from None
        finally:
            if owns_transport:
                transport.close()
