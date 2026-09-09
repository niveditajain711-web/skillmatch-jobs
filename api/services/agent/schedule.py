"""Optional daily shortlist: run search then batch-analyze drafts.

Still human-in-the-loop — never auto-submits applications.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from api.services.agent.batch import start_batch_analyze
from api.services.core.db import repository as repo
from api.services.core.db.session import session_scope
from api.services.run_service import execute_run_sync, is_running

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()
_last: dict[str, Any] = {
    "enabled": False,
    "status": "idle",
    "last_run_at": None,
    "last_search_run_id": None,
    "last_error": None,
    "next_run_at": None,
}


def get_schedule_status() -> dict[str, Any]:
    with _lock:
        return copy.deepcopy(_last)


def start_scheduler(config: dict[str, Any]) -> None:
    """Start daemon scheduler if agent.schedule.enabled."""
    global _thread
    sched = (config.get("agent") or {}).get("schedule") or {}
    if not sched.get("enabled"):
        with _lock:
            _last.update(
                {
                    "enabled": False,
                    "status": "disabled",
                    "next_run_at": None,
                }
            )
        return

    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _last["enabled"] = True
        _last["status"] = "waiting"
        _thread = threading.Thread(
            target=_loop, args=(copy.deepcopy(config),), daemon=True, name="agent-daily-schedule"
        )
        _thread.start()


def stop_scheduler() -> None:
    _stop.set()


def run_daily_shortlist_now(config: dict[str, Any]) -> dict[str, Any]:
    """Trigger one shortlist cycle (background). Returns immediate status."""
    with _lock:
        if _last.get("status", "").startswith("running"):
            raise RuntimeError("A shortlist cycle is already running")
        _last["status"] = "running_search"
        _last["last_error"] = None

    cfg = copy.deepcopy(config)

    def _worker() -> None:
        try:
            _run_cycle(cfg, triggered_by="manual")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Manual shortlist failed: %s", exc)
            with _lock:
                _last["last_error"] = str(exc)
                _last["status"] = "error"

    threading.Thread(target=_worker, daemon=True, name="agent-shortlist-now").start()
    with _lock:
        out = copy.deepcopy(_last)
    out["triggered_by"] = "manual"
    return out


def _loop(config: dict[str, Any]) -> None:
    while not _stop.is_set():
        sched = (config.get("agent") or {}).get("schedule") or {}
        if not sched.get("enabled"):
            break
        next_at = _next_daily_at(str(sched.get("daily_at") or "09:00"), sched.get("timezone"))
        with _lock:
            _last["next_run_at"] = next_at.isoformat()
            _last["status"] = "waiting"
        # Sleep in chunks so we can stop
        while not _stop.is_set():
            now = datetime.now(tz=next_at.tzinfo)
            remaining = (next_at - now).total_seconds()
            if remaining <= 0:
                break
            _stop.wait(min(remaining, 60))
        if _stop.is_set():
            break
        try:
            _run_cycle(config, triggered_by="schedule")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Daily shortlist failed: %s", exc)
            with _lock:
                _last["last_error"] = str(exc)
                _last["status"] = "error"
        # avoid double-fire in same minute
        _stop.wait(65)


def _next_daily_at(hhmm: str, tz_name: str | None) -> datetime:
    try:
        tz = ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
    except Exception:  # noqa: BLE001
        tz = datetime.now().astimezone().tzinfo
    hour, minute = 9, 0
    try:
        parts = hhmm.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except Exception:  # noqa: BLE001
        hour, minute = 9, 0
    now = datetime.now(tz=tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return target


def _run_cycle(config: dict[str, Any], *, triggered_by: str) -> dict[str, Any]:
    sched = (config.get("agent") or {}).get("schedule") or {}
    with _lock:
        _last["status"] = "running_search"
        _last["last_error"] = None

    if is_running():
        raise RuntimeError("A search is already running")

    result = execute_run_sync(config, refresh=bool(sched.get("refresh", False)))
    run_id = None
    if isinstance(result, dict):
        run_id = result.get("search_run_id") or result.get("run_id")
    if not run_id:
        with session_scope() as session:
            runs = repo.list_search_runs(session, limit=1)
            run_id = runs[0].id if runs else None

    with _lock:
        _last["last_search_run_id"] = run_id
        _last["last_run_at"] = datetime.now().isoformat()

    analyze_info = None
    if sched.get("analyze_after_search", True) and run_id:
        with _lock:
            _last["status"] = "running_analyze"
        analyze_info = start_batch_analyze(config, run_id=int(run_id))

    with _lock:
        _last["status"] = "idle"
        out = copy.deepcopy(_last)
    out["triggered_by"] = triggered_by
    out["analyze"] = analyze_info
    return out


__all__ = [
    "get_schedule_status",
    "run_daily_shortlist_now",
    "start_scheduler",
    "stop_scheduler",
]
