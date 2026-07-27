"""Persistence helpers for search runs, jobs, scores, and raw responses."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import JobRecord, JobScore, RawResponse, SearchRun
from src.models_dto import Job, ScoredJob


def _strip_secrets(config: dict[str, Any]) -> dict[str, Any]:
    snapshot = copy.deepcopy(config)
    jsearch = snapshot.get("sources", {}).get("jsearch", {})
    if isinstance(jsearch, dict) and "_api_key" in jsearch:
        jsearch["_api_key"] = "***" if jsearch["_api_key"] else None
    if "database" in snapshot and "url" in snapshot["database"]:
        snapshot["database"]["url"] = "***"
    return snapshot


def create_search_run(
    session: Session,
    *,
    keywords: str,
    config: dict[str, Any],
    resume_path: str,
    resume_skills: list[str],
) -> SearchRun:
    run = SearchRun(
        keywords=keywords,
        config_snapshot=_strip_secrets(config),
        status="running",
        resume_path=resume_path,
        resume_skills=resume_skills,
    )
    session.add(run)
    session.flush()
    return run


def finish_search_run(
    session: Session,
    run: SearchRun,
    *,
    status: str,
    jobs_fetched: int,
    jobs_scored: int,
    report_path: str | None,
) -> None:
    run.status = status
    run.jobs_fetched = jobs_fetched
    run.jobs_scored = jobs_scored
    run.report_path = report_path


def save_raw_response(
    session: Session,
    *,
    search_run_id: int | None,
    source: str,
    request_params: dict[str, Any],
    response_body: dict | list,
    cache_key: str | None,
) -> RawResponse:
    row = RawResponse(
        search_run_id=search_run_id,
        source=source,
        request_params=request_params,
        response_body=response_body,
        cache_key=cache_key,
    )
    session.add(row)
    session.flush()
    return row


def upsert_job(session: Session, job: Job) -> JobRecord:
    stmt = select(JobRecord).where(
        JobRecord.source == job.source,
        JobRecord.external_id == job.external_id,
    )
    existing = session.scalar(stmt)
    now = datetime.now(timezone.utc)
    if existing:
        existing.title = job.title
        existing.company = job.company
        existing.location = job.location
        existing.url = job.url
        existing.description = job.description
        existing.posted_at = job.posted_at
        existing.is_remote = job.is_remote
        existing.raw_json = job.raw_json
        existing.last_seen_at = now
        session.flush()
        return existing

    record = JobRecord(
        source=job.source,
        external_id=job.external_id,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        description=job.description,
        posted_at=job.posted_at,
        is_remote=job.is_remote,
        raw_json=job.raw_json,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(record)
    session.flush()
    return record


def save_scores(
    session: Session,
    search_run_id: int,
    scored_jobs: list[ScoredJob],
) -> None:
    for item in scored_jobs:
        job_row = upsert_job(session, item.job)
        session.add(
            JobScore(
                search_run_id=search_run_id,
                job_id=job_row.id,
                score=item.score,
                matched_keywords=item.matched_keywords,
                missing_keywords=item.missing_keywords,
            )
        )
    session.flush()


def load_recent_jobs(session: Session, limit: int = 200) -> list[Job]:
    """Load latest-seen jobs for --rescore-only mode."""
    stmt = select(JobRecord).order_by(JobRecord.last_seen_at.desc()).limit(limit)
    rows = session.scalars(stmt).all()
    jobs: list[Job] = []
    for row in rows:
        jobs.append(
            Job(
                source=row.source,
                external_id=row.external_id,
                title=row.title,
                company=row.company,
                location=row.location,
                url=row.url,
                description=row.description or "",
                posted_at=row.posted_at,
                is_remote=row.is_remote,
                raw_json=row.raw_json or {},
            )
        )
    return jobs