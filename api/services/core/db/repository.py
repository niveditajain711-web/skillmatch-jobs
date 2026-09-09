"""Persistence helpers for search runs, jobs, scores, and raw responses."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.services.core.db.models import (
    ApplicationDraft,
    ApplyQueueItem,
    JobRecord,
    JobScore,
    RawResponse,
    SearchRun,
)
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


def get_draft_for_job(
    session: Session, *, run_id: int, job_id: int
) -> ApplicationDraft | None:
    stmt = select(ApplicationDraft).where(
        ApplicationDraft.search_run_id == run_id,
        ApplicationDraft.job_id == job_id,
    )
    return session.scalars(stmt).first()


def get_draft_by_id(session: Session, draft_id: int) -> ApplicationDraft | None:
    return session.get(ApplicationDraft, draft_id)


def upsert_application_draft(
    session: Session,
    *,
    search_run_id: int,
    job_id: int,
    analysis: dict[str, Any],
) -> ApplicationDraft:
    draft = get_draft_for_job(session, run_id=search_run_id, job_id=job_id)
    if draft is None:
        draft = ApplicationDraft(search_run_id=search_run_id, job_id=job_id)
        session.add(draft)

    draft.fit_score = float(analysis.get("fit_score") or 0)
    draft.decision = str(analysis.get("decision") or "maybe")
    draft.reasons = analysis.get("reasons") or []
    draft.gaps = analysis.get("gaps") or []
    draft.red_flags = analysis.get("red_flags") or []
    draft.tailored_bullets = analysis.get("tailored_bullets") or []
    draft.cover_letter = str(analysis.get("cover_letter") or "")
    draft.form_answers = analysis.get("form_answers") or {}
    draft.provider = str(analysis.get("provider") or "")
    draft.model = str(analysis.get("model") or "")
    draft.updated_at = datetime.now(timezone.utc)
    session.flush()
    return draft


def ensure_queue_item(
    session: Session, *, draft_id: int, job_id: int
) -> ApplyQueueItem:
    stmt = select(ApplyQueueItem).where(ApplyQueueItem.draft_id == draft_id)
    item = session.scalars(stmt).first()
    if item:
        return item
    item = ApplyQueueItem(
        draft_id=draft_id,
        job_id=job_id,
        status="pending_review",
    )
    session.add(item)
    session.flush()
    return item


def get_queue_item(session: Session, queue_id: int) -> ApplyQueueItem | None:
    return session.get(ApplyQueueItem, queue_id)


def get_queue_item_for_draft(session: Session, draft_id: int) -> ApplyQueueItem | None:
    stmt = select(ApplyQueueItem).where(ApplyQueueItem.draft_id == draft_id)
    return session.scalars(stmt).first()


def list_apply_queue(
    session: Session, *, status: str | None = None, limit: int = 100
) -> list[tuple[ApplyQueueItem, ApplicationDraft, JobRecord]]:
    stmt = (
        select(ApplyQueueItem, ApplicationDraft, JobRecord)
        .join(ApplicationDraft, ApplyQueueItem.draft_id == ApplicationDraft.id)
        .join(JobRecord, ApplyQueueItem.job_id == JobRecord.id)
        .order_by(ApplyQueueItem.updated_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(ApplyQueueItem.status == status)
    return list(session.execute(stmt).all())


def update_queue_status(
    session: Session,
    queue_id: int,
    *,
    status: str,
    user_notes: str | None = None,
) -> ApplyQueueItem | None:
    item = get_queue_item(session, queue_id)
    if not item:
        return None
    item.status = status
    if user_notes is not None:
        item.user_notes = user_notes
    item.updated_at = datetime.now(timezone.utc)
    session.flush()
    return item

