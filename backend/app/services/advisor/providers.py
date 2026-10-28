"""LLM provider adapters.

The system is fully functional with the deterministic ``mock`` provider.
Gemini and any OpenAI-compatible endpoint (including local Ollama) are
optional.  Only computed facts and the user's question are sent to external
providers, never raw transaction rows, unless explicitly configured.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    latency_ms: int


class BaseProvider:
    name = "mock"
    model = "deterministic"

    def available(self) -> bool:
        return False

    def complete(self, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        raise LLMError("No language-model provider is configured")


class MockProvider(BaseProvider):
    """Used for offline operation and reproducible evaluation."""

    name = "mock"
    model = "clearpath-rules"

    def complete(self, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        raise LLMError("Mock provider does not generate free-form text")


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int, timeout: int):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        started = time.monotonic()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json" if json_mode else "text/plain",
            },
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            if not text:
                raise LLMError("Gemini returned an empty response")
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


class OpenAICompatProvider(BaseProvider):
    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str, model: str, temperature: float, max_tokens: int, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.base_url)

    def complete(self, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        started = time.monotonic()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            if not text:
                raise LLMError("Provider returned an empty response")
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"OpenAI-compatible request failed: {exc}") from exc
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def get_provider(app) -> BaseProvider:
    configured = str(app.config.get("LLM_PROVIDER", "auto")).lower()
    gemini_key = str(app.config.get("GEMINI_API_KEY", ""))
    base_url = str(app.config.get("LLM_BASE_URL", ""))
    model = str(app.config.get("LLM_MODEL", ""))
    temperature = float(app.config.get("LLM_TEMPERATURE", 0.2))
    max_tokens = int(app.config.get("LLM_MAX_TOKENS", 900))
    timeout = int(app.config.get("LLM_TIMEOUT_SECONDS", 25))

    if configured == "mock":
        return MockProvider()
    if configured == "gemini" or (configured == "auto" and gemini_key):
        return GeminiProvider(
            gemini_key, model or str(app.config.get("GEMINI_MODEL", "gemini-2.0-flash")),
            temperature, max_tokens, timeout,
        )
    if configured in {"openai", "ollama", "openai-compatible", "auto"} and base_url:
        return OpenAICompatProvider(
            base_url, str(app.config.get("LLM_API_KEY", "")), model or "llama3.1",
            temperature, max_tokens, timeout,
        )
    return MockProvider()


def provider_status(app) -> dict:
    provider = get_provider(app)
    return {
        "provider": provider.name,
        "model": provider.model,
        "available": provider.available(),
        "mode": "llm" if provider.available() else "deterministic",
        "note": (
            "Answers are composed from verified tool outputs."
            if provider.available()
            else "No API key configured. The deterministic advisor is active; every answer is still computed from your data."
        ),
    }


def parse_json(text: str) -> dict:
    """Parse a JSON object from a model response, tolerating code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMError("Model did not return valid JSON")
