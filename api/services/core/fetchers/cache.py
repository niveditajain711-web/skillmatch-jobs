"""File-based response cache to protect free API quotas."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def make_cache_key(source: str, params: dict[str, Any]) -> str:
    payload = json.dumps({"source": source, "params": params}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, cache_dir: str | Path, ttl_hours: int = 24, enabled: bool = True):
        self.enabled = enabled
        self.ttl = timedelta(hours=ttl_hours)
        self.dir = Path(cache_dir)
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, cache_key: str) -> Path:
        return self.dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> dict | list | None:
        if not self.enabled:
            return None
        path = self._path(cache_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(data["fetched_at"])
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - fetched_at > self.ttl:
                return None
            return data.get("body")
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    def set(self, cache_key: str, body: dict | list, meta: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "meta": meta or {},
            "body": body,
        }
        self._path(cache_key).write_text(json.dumps(payload, default=str), encoding="utf-8")