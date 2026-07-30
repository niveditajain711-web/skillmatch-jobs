"""Search run execution for API."""

from __future__ import annotations

import copy
import threading
from typing import Any

from api.services.core.orchestrator import run_pipeline

_lock = threading.Lock()
_running = False
_last_result: dict[str, Any] | None = None
_last_error: str | None = None


def merge_config(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    search = overrides.get("search") or {}
    for k, v in search.items():
        if v is not None:
            cfg.setdefault("search", {})[k] = v
    sources = overrides.get("sources") or {}
    for name, enabled in sources.items():
        if enabled is not None:
            cfg.setdefault("sources", {}).setdefault(name, {})["enabled"] = enabled
    scoring = overrides.get("scoring") or {}
    for k, v in scoring.items():
        if v is not None:
            cfg.setdefault("scoring", {})[k] = v
    # Preserve API keys injected by load_config (not in yaml)
    base_jsearch = base.get("sources", {}).get("jsearch", {})
    if base_jsearch.get("_api_key"):
        cfg.setdefault("sources", {}).setdefault("jsearch", {})["_api_key"] = base_jsearch[
            "_api_key"
        ]
    return cfg


def is_running() -> bool:
    return _running


def get_last_result() -> dict[str, Any] | None:
    return _last_result


def get_last_error() -> str | None:
    return _last_error


def start_run_background(
    config: dict[str, Any],
    *,
    refresh: bool = False,
    rescore_only: bool = False,
    overrides: dict[str, Any] | None = None,
) -> None:
    global _running, _last_result, _last_error
    with _lock:
        if _running:
            raise RuntimeError("A search is already running. Wait for it to finish.")
        _running = True
        _last_result = None
        _last_error = None

    merged = merge_config(config, overrides or {})

    def _worker() -> None:
        global _running, _last_result, _last_error
        try:
            _last_result = run_pipeline(merged, refresh=refresh, rescore_only=rescore_only)
        except Exception as exc:  # noqa: BLE001
            _last_error = str(exc)
        finally:
            with _lock:
                _running = False

    threading.Thread(target=_worker, daemon=True).start()


def execute_run_sync(
    config: dict[str, Any],
    *,
    refresh: bool = False,
    rescore_only: bool = False,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = merge_config(config, overrides or {})
    return run_pipeline(merged, refresh=refresh, rescore_only=rescore_only)
