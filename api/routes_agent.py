"""AI apply-agent API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_config, get_db
from api.schemas import (
    AgentStatusResponse,
    AnalyzeJobRequest,
    ApplicationDraftResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeStatusResponse,
    BrowserAssistStatusResponse,
    QueueUpdateRequest,
    ScheduleStatusResponse,
)
from api.services.agent.batch import get_batch_status, start_batch_analyze
from api.services.agent.browser_assist import BrowserAssistError, get_assist_status
from api.services.agent.llm import LLMError
from api.services.agent.schedule import get_schedule_status, run_daily_shortlist_now
from api.services.agent.service import (
    analyze_run_job,
    build_clipboard_pack,
    draft_to_dict,
    open_apply_pack,
    start_assisted_browser_fill,
)
from api.services.core.db import repository as repo

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

ALLOWED_QUEUE_STATUSES = {
    "pending_review",
    "approved",
    "skipped",
    "opened",
    "applied",
    "not_applied",
    "failed",
}

NOT_APPLIED_REASONS = {
    "no_link",
    "job_closed",
    "not_eligible",
    "login_wall",
    "form_blocked",
    "duplicate",
    "other",
}


def _draft_response(draft, queue=None, job=None, *, include_pack: bool = False) -> ApplicationDraftResponse:
    data = draft_to_dict(draft, queue)
    if job is not None:
        data.update(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "source": job.source,
            }
        )
    if include_pack:
        data["clipboard_pack"] = build_clipboard_pack(
            draft,
            title=job.title if job else None,
            company=job.company if job else None,
            url=job.url if job else None,
        )
    return ApplicationDraftResponse(**data)


@router.get("/status", response_model=AgentStatusResponse)
def agent_status(config: dict = Depends(get_config)) -> AgentStatusResponse:
    agent = config.get("agent") or {}
    provider = str(agent.get("provider") or "ollama")
    model = str(
        agent.get("model")
        or {
            "ollama": "llama3.1:8b",
            "groq": "llama-3.1-8b-instant",
            "gemini": "gemini-2.0-flash",
        }.get(provider, "llama3.1:8b")
    )
    return AgentStatusResponse(
        enabled=bool(agent.get("enabled", True)),
        provider=provider,
        model=model,
        require_human_approval=bool(agent.get("require_human_approval", True)),
        max_jobs_per_run=int(agent.get("max_jobs_per_run") or 15),
        min_keyword_score=float(agent.get("min_keyword_score") or 40),
        browser_assist_enabled=bool((agent.get("browser_assist") or {}).get("enabled", True)),
        schedule_enabled=bool((agent.get("schedule") or {}).get("enabled", False)),
        schedule_daily_at=str((agent.get("schedule") or {}).get("daily_at") or "09:00"),
    )


@router.post(
    "/runs/{run_id}/jobs/{job_id}/analyze",
    response_model=ApplicationDraftResponse,
)
def analyze_job(
    run_id: int,
    job_id: int,
    body: AnalyzeJobRequest | None = None,
    db: Session = Depends(get_db),
    config: dict = Depends(get_config),
) -> ApplicationDraftResponse:
    force = bool(body.force) if body else False
    try:
        draft = analyze_run_job(db, config, run_id=run_id, job_id=job_id, force=force)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Agent analysis failed: {exc}") from exc

    queue = repo.get_queue_item_for_draft(db, draft.id)
    job = repo.get_job_by_id(db, job_id)
    return _draft_response(draft, queue, job, include_pack=True)


@router.post(
    "/runs/{run_id}/analyze",
    response_model=BatchAnalyzeStatusResponse,
)
def analyze_run_batch(
    run_id: int,
    body: BatchAnalyzeRequest | None = None,
    config: dict = Depends(get_config),
) -> BatchAnalyzeStatusResponse:
    """Analyze top N jobs from a search run in the background."""
    req = body or BatchAnalyzeRequest()
    try:
        status = start_batch_analyze(
            config,
            run_id=run_id,
            max_jobs=req.max_jobs,
            min_score=req.min_score,
            force=req.force,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return BatchAnalyzeStatusResponse(**status)


@router.get(
    "/runs/{run_id}/analyze",
    response_model=BatchAnalyzeStatusResponse,
)
def get_analyze_run_status(run_id: int) -> BatchAnalyzeStatusResponse:
    status = get_batch_status(run_id)
    if not status:
        # Idle is normal before the first "Analyze top N" click — not an error.
        return BatchAnalyzeStatusResponse(run_id=run_id, status="idle")
    return BatchAnalyzeStatusResponse(**status)


@router.get(
    "/runs/{run_id}/jobs/{job_id}/draft",
    response_model=ApplicationDraftResponse,
)
def get_job_draft(
    run_id: int,
    job_id: int,
    db: Session = Depends(get_db),
) -> ApplicationDraftResponse:
    draft = repo.get_draft_for_job(db, run_id=run_id, job_id=job_id)
    if not draft:
        raise HTTPException(404, "No AI draft for this job yet. Run Analyze first.")
    queue = repo.get_queue_item_for_draft(db, draft.id)
    job = repo.get_job_by_id(db, job_id)
    return _draft_response(draft, queue, job, include_pack=True)


@router.get("/queue", response_model=list[ApplicationDraftResponse])
def list_queue(
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[ApplicationDraftResponse]:
    rows = repo.list_apply_queue(db, status=status, limit=limit)
    return [_draft_response(draft, queue, job, include_pack=True) for queue, draft, job in rows]


@router.patch("/queue/{queue_id}", response_model=ApplicationDraftResponse)
def update_queue(
    queue_id: int,
    body: QueueUpdateRequest,
    db: Session = Depends(get_db),
) -> ApplicationDraftResponse:
    status = body.status.strip().lower()
    if status not in ALLOWED_QUEUE_STATUSES:
        raise HTTPException(
            400,
            f"Invalid status. Allowed: {', '.join(sorted(ALLOWED_QUEUE_STATUSES))}",
        )

    reason = (body.not_applied_reason or "").strip().lower() or None
    notes = body.user_notes
    if status == "not_applied":
        if not reason or reason not in NOT_APPLIED_REASONS:
            raise HTTPException(
                400,
                "not_applied requires not_applied_reason. Allowed: "
                + ", ".join(sorted(NOT_APPLIED_REASONS)),
            )
        if reason == "other" and not (notes and str(notes).strip()):
            raise HTTPException(400, "Reason 'other' requires user_notes.")
    else:
        reason = None

    item = repo.update_queue_status(
        db,
        queue_id,
        status=status,
        user_notes=notes,
        not_applied_reason=reason,
    )
    if not item:
        raise HTTPException(404, "Queue item not found")
    draft = repo.get_draft_by_id(db, item.draft_id)
    job = repo.get_job_by_id(db, item.job_id)
    return _draft_response(draft, item, job, include_pack=True)


@router.post("/queue/{queue_id}/open-apply", response_model=ApplicationDraftResponse)
def open_apply(
    queue_id: int,
    db: Session = Depends(get_db),
) -> ApplicationDraftResponse:
    """Mark opened and return apply URL + clipboard pack (no auto-submit)."""
    try:
        data = open_apply_pack(db, queue_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return ApplicationDraftResponse(**data)


@router.post(
    "/queue/{queue_id}/browser-assist",
    response_model=BrowserAssistStatusResponse,
)
def browser_assist(
    queue_id: int,
    db: Session = Depends(get_db),
    config: dict = Depends(get_config),
) -> BrowserAssistStatusResponse:
    """Open headed browser, prefills known ATS fields. Never clicks Submit."""
    try:
        status = start_assisted_browser_fill(db, config, queue_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except BrowserAssistError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Browser assist failed: {exc}") from exc
    return BrowserAssistStatusResponse(**status)


@router.get(
    "/queue/{queue_id}/browser-assist",
    response_model=BrowserAssistStatusResponse,
)
def browser_assist_status(queue_id: int) -> BrowserAssistStatusResponse:
    status = get_assist_status(queue_id)
    if not status:
        raise HTTPException(404, "No browser assist started for this queue item yet.")
    return BrowserAssistStatusResponse(**status)


@router.get("/schedule", response_model=ScheduleStatusResponse)
def schedule_status() -> ScheduleStatusResponse:
    return ScheduleStatusResponse(**get_schedule_status())


@router.post("/schedule/run-now", response_model=ScheduleStatusResponse)
def schedule_run_now(config: dict = Depends(get_config)) -> ScheduleStatusResponse:
    """Run one search + batch analyze cycle now (still no auto-submit)."""
    try:
        result = run_daily_shortlist_now(config)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Shortlist failed: {exc}") from exc
    # Drop nested analyze blob from response model
    payload = {k: v for k, v in result.items() if k != "analyze"}
    return ScheduleStatusResponse(**payload)
