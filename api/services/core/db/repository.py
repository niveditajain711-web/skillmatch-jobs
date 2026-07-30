"""Persistence helpers for search runs, jobs, scores, and raw responses."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.services.core.db.models import JobRecord, JobScore, RawResponse, SearchRun
from api.services.core.models_dto import Job, ScoredJob


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


def list_search_runs(session: Session, limit: int = 50) -> list[SearchRun]:
    stmt = select(SearchRun).order_by(SearchRun.started_at.desc()).limit(limit)
    return list(session.scalars(stmt).all())


def get_search_run(session: Session, run_id: int) -> SearchRun | None:
    return session.get(SearchRun, run_id)


def get_run_jobs(
    session: Session,
    run_id: int,
    *,
    min_score: float | None = None,
    source: str | None = None,
    limit: int = 200,
) -> list[tuple[JobScore, JobRecord]]:
    stmt = (
        select(JobScore, JobRecord)
        .join(JobRecord, JobScore.job_id == JobRecord.id)
        .where(JobScore.search_run_id == run_id)
        .order_by(JobScore.score.desc())
        .limit(limit)
    )
    if min_score is not None:
        stmt = stmt.where(JobScore.score >= min_score)
    if source:
        stmt = stmt.where(JobRecord.source == source)
    return list(session.execute(stmt).all())


def get_run_job_detail(
    session: Session, run_id: int, job_id: int
) -> tuple[JobScore, JobRecord] | None:
    stmt = (
        select(JobScore, JobRecord)
        .join(JobRecord, JobScore.job_id == JobRecord.id)
        .where(JobScore.search_run_id == run_id, JobRecord.id == job_id)
    )
    row = session.execute(stmt).first()
    return row if row else None


def get_job_by_id(session: Session, job_id: int) -> JobRecord | None:
    return session.get(JobRecord, job_id)


def get_run_gaps(session: Session, run_id: int) -> list[tuple[str, int]]:
    """Return (skill, count) for missing keywords across a run."""
    from collections import Counter

    stmt = select(JobScore).where(JobScore.search_run_id == run_id)
    counter: Counter[str] = Counter()
    for score in session.scalars(stmt):
        for skill in score.missing_keywords or []:
            counter[skill] += 1
    return counter.most_common()