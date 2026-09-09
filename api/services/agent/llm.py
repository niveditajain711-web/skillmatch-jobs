"""LLM provider abstractions for the apply agent."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

import requests


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    provider: str
    model: str

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        ...


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise LLMError("Empty LLM response")
    # Prefer fenced json block
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON root must be an object")
    return data


class OllamaClient:
    provider = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        timeout_seconds: int = 600,
    ):
        self.model = model
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip(
            "/"
        )
        self.timeout_seconds = max(60, int(timeout_seconds))

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "keep_alive": "10m",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": 0.3,
                "num_predict": 1024,  # cap output length for faster CPU runs
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_seconds)
            if resp.status_code == 404:
                raise LLMError(
                    f"Ollama model '{self.model}' is not installed. "
                    f"Run: ollama pull {self.model}"
                )
            resp.raise_for_status()
        except LLMError:
            raise
        except requests.exceptions.ReadTimeout as exc:
            raise LLMError(
                f"Ollama timed out after {self.timeout_seconds}s for model '{self.model}'. "
                f"On CPU, 8B models are slow for long JDs. Options: "
                f"(1) pull a smaller model: ollama pull llama3.2:3b and set agent.model: llama3.2:3b; "
                f"(2) raise agent.ollama_timeout_seconds in config.yaml; "
                f"(3) use Groq/Gemini. Detail: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise LLMError(
                f"Ollama request failed ({self.base_url}). Is Ollama running? "
                f"Detail: {exc}"
            ) from exc
        body = resp.json()
        content = (body.get("message") or {}).get("content") or ""
        return _extract_json(content)


class GroqClient:
    provider = "groq"

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or ""
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not set in .env")

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"Groq request failed: {exc}") from exc
        content = resp.json()["choices"][0]["message"]["content"]
        return _extract_json(content)


class GeminiClient:
    provider = "gemini"

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or ""
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set in .env")

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)
        return _extract_json(content)


def get_llm_client(config: dict[str, Any]) -> LLMClient:
    agent = config.get("agent") or {}
    if not agent.get("enabled", True):
        raise LLMError("Agent is disabled in config.yaml (agent.enabled: false)")
    provider = str(agent.get("provider") or "ollama").lower().strip()
    model = str(agent.get("model") or _default_model(provider))
    if provider == "ollama":
        return OllamaClient(
            model=model,
            base_url=agent.get("ollama_base_url"),
            timeout_seconds=int(agent.get("ollama_timeout_seconds") or 600),
        )
    if provider == "groq":
        return GroqClient(model=model)
    if provider == "gemini":
        return GeminiClient(model=model)
    raise LLMError(f"Unsupported agent.provider: {provider}")


def _default_model(provider: str) -> str:
    return {
        "ollama": "llama3.1:8b",
        "groq": "llama-3.1-8b-instant",
        "gemini": "gemini-2.0-flash",
    }.get(provider, "llama3.1:8b")
