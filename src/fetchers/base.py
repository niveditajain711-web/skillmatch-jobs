"""Fetcher interface and shared utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import requests

from src.fetchers.cache import ResponseCache, make_cache_key
from src.models_dto import Job


def format_api_error(exc: Exception) -> str:
    """Return a readable message; RapidAPI often hides the real cause behind 405."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        resp = exc.response
        try:
            body = resp.json()
            message = body.get("message") or body.get("error") or body.get("detail")
            if message:
                return f"{resp.status_code} {message}"
        except ValueError:
            pass
        text = (resp.text or "").strip()
        if text:
            return f"{resp.status_code} {text[:300]}"
        return f"{resp.status_code} {resp.reason}"
    return str(exc)


class BaseFetcher(ABC):
    name: str = "base"

    def __init__(self, config: dict[str, Any], cache: ResponseCache, refresh: bool = False):
        self.config = config
        self.cache = cache
        self.refresh = refresh
        self.last_request_params: dict[str, Any] = {}
        self.last_raw_body: dict | list | None = None
        self.last_cache_key: str | None = None
        self.used_cache = False

    @abstractmethod
    def fetch(self) -> list[Job]:
        raise NotImplementedError

    def _load_or_fetch_json(
        self,
        params: dict[str, Any],
        fetch_fn,
    ) -> dict | list:
        cache_key = make_cache_key(self.name, params)
        self.last_request_params = params
        self.last_cache_key = cache_key
        self.used_cache = False

        if not self.refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.last_raw_body = cached
                self.used_cache = True
                return cached

        body = fetch_fn()
        self.last_raw_body = body
        self.cache.set(cache_key, body, meta={"source": self.name, "params": params})
        return body


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # JSearch often returns unix epoch seconds
        try:
            return datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text.replace("+00:00", "Z"), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def truncate(text: str, limit: int = 50000) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit]