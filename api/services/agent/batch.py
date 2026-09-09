"""Background batch analyze for a search run."""

from __future__ import annotations

import copy
import threading
from typing import Any

from api.services.agent.service import analyze_run_job
from api.services.core.db import repository as repo
from api.services.core.db.session import session_scope

_lock = threading.Lock()
# run_id -> status dict
_jobs: dict[int, dict[str, Any]] = {}


def get_batch_status(run_id: int) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(run_id)
        return copy.deepcopy(job) if job else None


def is_batch_running(run_id: int | None = None) -> bool:
    with _lock:
        if run_id is not None:
            job = _jobs.get(run_id)
            return bool(job and job.get("status") == "running")
        return any(j.get("status") == "running" for j in _jobs.values())


def start_batch_analyze(
    config: dict[str, Any],
    *,
    run_id: int,
    max_jobs: int | None = None,
    min_score: float | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Start analyzing top jobs for a run in a background thread."""
    agent = config.get("agent") or {}
    if not agent.get("enabled", True):
        raise RuntimeError("Agent is disabled in config.yaml")

    limit = int(max_jobs if max_jobs is not None else agent.get("max_jobs_per_run") or 15)
    score_floor = float(
        min_score if min_score is not None else agent.get("min_keyword_score") or 0
    )

    with _lock:
        if any(j.get("status") == "running" for j in _jobs.values()):
            raise RuntimeError("An agent batch analyze is already running. Wait for it to finish.")
        _jobs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "total": 0,
            "analyzed": 0,
            "skipped_existing": 0,
            "errors": [],
            "job_ids": [],
            "force": force,
            "min_score": score_floor,
            "max_jobs": limit,
        }

    cfg = copy.deepcopy(config)

    def _worker() -> None:
        analyzed = 0
        skipped = 0
        errors: list[str] = []
        job_ids: list[int] = []
        try:
            candidate_ids: list[int] = []
            with session_scope() as session:
                run = repo.get_search_run(session, run_id)
                if not run:
                    raise LookupError(f"Search run {run_id} not found")
                rows = repo.get_run_jobs(
                    session, run_id, min_score=score_floor, limit=limit * 3
                )
                # Copy IDs while session is open (avoid DetachedInstanceError)
                candidate_ids = [job.id for _score, job in rows]

            selected: list[int] = []
            with session_scope() as session:
                for job_id in candidate_ids:
                    if len(selected) >= limit:
                        break
                    if not force:
                        existing = repo.get_draft_for_job(
                            session, run_id=run_id, job_id=job_id
                        )
                        if existing:
                            skipped += 1
                            continue
                    selected.append(job_id)

            with _lock:
                if run_id in _jobs:
                    _jobs[run_id]["total"] = len(selected)
                    _jobs[run_id]["skipped_existing"] = skipped
                    _jobs[run_id]["job_ids"] = list(selected)

            if not selected:
                with _lock:
                    if run_id in _jobs:
                        _jobs[run_id]["status"] = "completed"
                        _jobs[run_id]["errors"] = (
                            [
                                "No jobs to analyze (none above min score, or all already have drafts). "
                                "Lower min score / raise max_jobs, or re-run with force."
                            ]
                            if skipped == 0 and not candidate_ids
                            else []
                        )
                        if skipped and not selected:
                            _jobs[run_id]["errors"] = [
                                f"Skipped {skipped} job(s) that already have drafts. "
                                "Re-analyze from Job Detail if you want to refresh one."
                            ]
                return

            for job_id in selected:
                try:
                    with session_scope() as session:
                        analyze_run_job(
                            session, cfg, run_id=run_id, job_id=job_id, force=force
                        )
                    analyzed += 1
                    job_ids.append(job_id)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"job {job_id}: {exc}")
                with _lock:
                    if run_id in _jobs:
                        _jobs[run_id]["analyzed"] = analyzed
                        _jobs[run_id]["errors"] = list(errors)
                        _jobs[run_id]["job_ids"] = list(job_ids)

            with _lock:
                if run_id in _jobs:
                    _jobs[run_id]["status"] = (
                        "completed" if not errors else "completed_with_errors"
                    )
                    _jobs[run_id]["analyzed"] = analyzed
                    _jobs[run_id]["skipped_existing"] = skipped
                    _jobs[run_id]["errors"] = errors
        except Exception as exc:  # noqa: BLE001
            with _lock:
                if run_id in _jobs:
                    _jobs[run_id]["status"] = "failed"
                    _jobs[run_id]["errors"] = [str(exc)]
                    _jobs[run_id]["analyzed"] = analyzed
                    _jobs[run_id]["skipped_existing"] = skipped

    threading.Thread(target=_worker, daemon=True, name=f"agent-batch-{run_id}").start()
    with _lock:
        return copy.deepcopy(_jobs[run_id])


__all__ = ["get_batch_status", "is_batch_running", "start_batch_analyze"]
