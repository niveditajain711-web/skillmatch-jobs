"""API route handlers."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_config, get_db, reload_config
from api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    DashboardResponse,
    GapItem,
    JobDetailResponse,
    JobScoreResponse,
    ResumeResponse,
    RunResponse,
    SearchSettingsUpdate,
    SettingsResponse,
)
from api.services.run_service import is_running, start_run_background
from api.services.core.config import _project_root
from api.services.core.db import repository as repo
from api.services.core.parsing.resume import load_resume

router = APIRouter(prefix="/api/v1")


def _run_to_response(run) -> RunResponse:
    return RunResponse(
        id=run.id,
        started_at=run.started_at,
        keywords=run.keywords,
        status=run.status,
        jobs_fetched=run.jobs_fetched,
        jobs_scored=run.jobs_scored,
        report_path=run.report_path,
        resume_skills=run.resume_skills,
    )


def _job_row_to_response(score, job) -> JobScoreResponse:
    return JobScoreResponse(
        job_id=job.id,
        score=score.score,
        matched_keywords=score.matched_keywords or [],
        missing_keywords=score.missing_keywords or [],
        title=job.title,
        company=job.company,
        location=job.location,
        source=job.source,
        url=job.url,
        is_remote=job.is_remote,
        posted_at=job.posted_at,
    )


@router.get("/status")
def run_status() -> dict:
    return {"running": is_running()}


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    runs = repo.list_search_runs(db, limit=1)
    if not runs:
        return DashboardResponse(latest_run=None, top_matches=[], avg_score=None, gaps=[])

    latest = runs[0]
    rows = repo.get_run_jobs(db, latest.id, limit=5)
    all_rows = repo.get_run_jobs(db, latest.id, limit=500)
    scores = [r[0].score for r in all_rows]
    avg = round(sum(scores) / len(scores), 2) if scores else None
    gaps = [
        GapItem(skill=s, jobs_missing_count=c)
        for s, c in repo.get_run_gaps(db, latest.id)[:10]
    ]

    return DashboardResponse(
        latest_run=_run_to_response(latest),
        top_matches=[_job_row_to_response(s, j) for s, j in rows],
        avg_score=avg,
        gaps=gaps,
    )


@router.get("/runs", response_model=list[RunResponse])
def list_runs(limit: int = 50, db: Session = Depends(get_db)) -> list[RunResponse]:
    return [_run_to_response(r) for r in repo.list_search_runs(db, limit=limit)]


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)) -> RunResponse:
    run = repo.get_search_run(db, run_id)
    if not run:
        raise HTTPException(404, "Search run not found")
    return _run_to_response(run)


@router.post("/runs", response_model=CreateRunResponse)
def create_run(
    body: CreateRunRequest,
) -> CreateRunResponse:
    if body.refresh and body.rescore_only:
        raise HTTPException(400, "Use either refresh or rescore_only, not both")
    if is_running():
        raise HTTPException(409, "A search is already running")

    config = reload_config()

    overrides: dict = {}
    if body.search:
        # exclude_unset keeps explicit nulls (e.g. clear years_of_experience for this run)
        overrides["search"] = body.search.model_dump(exclude_unset=True)
    if body.sources:
        overrides["sources"] = body.sources.model_dump(exclude_none=True)
    if body.scoring:
        overrides["scoring"] = body.scoring.model_dump(exclude_none=True)

    start_run_background(
        config,
        refresh=body.refresh,
        rescore_only=body.rescore_only,
        overrides=overrides or None,
    )
    return CreateRunResponse(
        run_id=0,
        status="running",
        message="Search started. Poll GET /api/v1/runs for the latest run status.",
    )


@router.get("/runs/{run_id}/jobs", response_model=list[JobScoreResponse])
def list_run_jobs(
    run_id: int,
    min_score: float | None = None,
    source: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[JobScoreResponse]:
    if not repo.get_search_run(db, run_id):
        raise HTTPException(404, "Search run not found")
    rows = repo.get_run_jobs(db, run_id, min_score=min_score, source=source, limit=limit)
    return [_job_row_to_response(s, j) for s, j in rows]


@router.get("/runs/{run_id}/jobs/{job_id}", response_model=JobDetailResponse)
def get_run_job(run_id: int, job_id: int, db: Session = Depends(get_db)) -> JobDetailResponse:
    row = repo.get_run_job_detail(db, run_id, job_id)
    if not row:
        raise HTTPException(404, "Job not found for this run")
    score, job = row
    return JobDetailResponse(
        job_id=job.id,
        run_id=run_id,
        score=score.score,
        matched_keywords=score.matched_keywords or [],
        missing_keywords=score.missing_keywords or [],
        title=job.title,
        company=job.company,
        location=job.location,
        source=job.source,
        url=job.url,
        description=job.description or "",
        is_remote=job.is_remote,
        posted_at=job.posted_at,
    )


@router.get("/runs/{run_id}/gaps", response_model=list[GapItem])
def get_run_gaps(run_id: int, db: Session = Depends(get_db)) -> list[GapItem]:
    if not repo.get_search_run(db, run_id):
        raise HTTPException(404, "Search run not found")
    return [
        GapItem(skill=s, jobs_missing_count=c) for s, c in repo.get_run_gaps(db, run_id)
    ]


@router.get("/resume", response_model=ResumeResponse)
def get_resume(config: dict = Depends(get_config)) -> ResumeResponse:
    resume_cfg = config.get("resume", {})
    try:
        resume = load_resume(
            resume_cfg.get("path", "./data/resume.pdf"),
            resume_cfg.get("text_fallback_path", "./data/resume.txt"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    preview = resume.text[:500].replace("\n", " ").strip()
    return ResumeResponse(
        source_path=resume.source_path,
        skills=resume.skills,
        text_preview=preview,
    )


@router.post("/resume", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    config: dict = Depends(get_config),
) -> ResumeResponse:
    root = _project_root()
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)

    suffix = Path(file.filename or "resume.pdf").suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(400, "Upload a PDF or text file")

    dest = data_dir / ("resume.pdf" if suffix == ".pdf" else "resume.txt")
    content = await file.read()
    dest.write_bytes(content)

    resume_cfg = config.get("resume", {})
    resume = load_resume(
        str(dest),
        resume_cfg.get("text_fallback_path", "./data/resume.txt"),
    )
    preview = resume.text[:500].replace("\n", " ").strip()
    return ResumeResponse(
        source_path=resume.source_path,
        skills=resume.skills,
        text_preview=preview,
    )


@router.get("/settings", response_model=SettingsResponse)
def get_settings(config: dict = Depends(get_config)) -> SettingsResponse:
    return SettingsResponse(
        search=config.get("search", {}),
        sources={
            k: {"enabled": v.get("enabled", False)}
            for k, v in config.get("sources", {}).items()
        },
        scoring=config.get("scoring", {}),
        cache=config.get("cache", {}),
    )


@router.put("/settings/scoring", response_model=SettingsResponse)
def update_scoring(
    body: dict,
    config: dict = Depends(get_config),
) -> SettingsResponse:
    root = _project_root()
    path = root / "config.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw.setdefault("scoring", {}).update(body)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False)
    config["scoring"] = raw["scoring"]
    return get_settings(config)


@router.put("/settings/search", response_model=SettingsResponse)
def update_search_settings(body: SearchSettingsUpdate) -> SettingsResponse:
    """Persist search filters (experience, country, remote) from the UI."""
    root = _project_root()
    path = root / "config.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    search = raw.setdefault("search", {})
    data = body.model_dump(exclude_unset=True)

    for clear_flag, key in (
        ("clear_years_of_experience", "years_of_experience"),
        ("clear_experience_min", "experience_min"),
        ("clear_experience_max", "experience_max"),
    ):
        if data.pop(clear_flag, False):
            search.pop(key, None)

    for key in (
        "years_of_experience",
        "experience_min",
        "experience_max",
        "keep_unknown_experience",
        "experience_tolerance",
        "remote_only",
        "countries",
    ):
        if key in data and data[key] is not None:
            search[key] = data[key]

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False)

    config = reload_config()
    return get_settings(config)
