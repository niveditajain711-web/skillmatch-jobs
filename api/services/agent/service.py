"""Agent orchestration: analyze jobs, manage apply queue."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from api.services.agent.analyze import analyze_job_fit
from api.services.agent.llm import LLMError, get_llm_client
from api.services.core.db import repository as repo
from api.services.core.db.models import ApplicationDraft, ApplyQueueItem
from api.services.core.parsing.resume import load_resume


def _load_resume_bundle(config: dict[str, Any]) -> tuple[str, list[str]]:
    resume_cfg = config.get("resume", {})
    resume = load_resume(
        resume_cfg.get("path", "./data/resume.pdf"),
        resume_cfg.get("text_fallback_path", "./data/resume.txt"),
    )
    return resume.text, resume.skills


def analyze_run_job(
    session: Session,
    config: dict[str, Any],
    *,
    run_id: int,
    job_id: int,
    force: bool = False,
) -> ApplicationDraft:
    """Analyze one job from a search run; upsert draft + queue row."""
    row = repo.get_run_job_detail(session, run_id, job_id)
    if not row:
        raise LookupError("Job not found for this run")
    _score, job = row

    if not force:
        existing = repo.get_draft_for_job(session, run_id=run_id, job_id=job_id)
        if existing:
            return existing

    resume_text, skills = _load_resume_bundle(config)
    client = get_llm_client(config)
    result = analyze_job_fit(
        resume_text=resume_text,
        resume_skills=skills,
        job_title=job.title,
        company=job.company,
        location=job.location,
        description=job.description or "",
        config=config,
        client=client,
    )

    draft = repo.upsert_application_draft(
        session,
        search_run_id=run_id,
        job_id=job_id,
        analysis=result,
    )
    repo.ensure_queue_item(session, draft_id=draft.id, job_id=job_id)
    session.flush()
    return draft


def build_clipboard_pack(
    draft: ApplicationDraft,
    *,
    title: str | None = None,
    company: str | None = None,
    url: str | None = None,
) -> str:
    """One pasteable block: cover letter + bullets + form answers."""
    lines: list[str] = []
    header_bits = [b for b in [title, company] if b]
    if header_bits:
        lines.append(" · ".join(header_bits))
        lines.append("")
    if url:
        lines.append(f"Apply URL: {url}")
        lines.append("")
    lines.append(f"Decision: {draft.decision} · Fit {draft.fit_score:.0f}/100")
    lines.append("")
    if draft.cover_letter:
        lines.append("--- Cover letter ---")
        lines.append(draft.cover_letter.strip())
        lines.append("")
    bullets = draft.tailored_bullets or []
    if bullets:
        lines.append("--- Tailored bullets ---")
        for b in bullets:
            lines.append(f"• {b}")
        lines.append("")
    answers = draft.form_answers or {}
    if answers:
        lines.append("--- Form answers ---")
        for key, val in answers.items():
            if val:
                label = str(key).replace("_", " ")
                lines.append(f"{label}: {val}")
        lines.append("")
    if draft.gaps:
        lines.append("--- Gaps to be honest about ---")
        for g in draft.gaps:
            lines.append(f"• {g}")
    return "\n".join(lines).strip() + "\n"


def draft_to_dict(draft: ApplicationDraft, queue: ApplyQueueItem | None = None) -> dict[str, Any]:
    return {
        "id": draft.id,
        "search_run_id": draft.search_run_id,
        "job_id": draft.job_id,
        "fit_score": draft.fit_score,
        "decision": draft.decision,
        "reasons": draft.reasons or [],
        "gaps": draft.gaps or [],
        "red_flags": draft.red_flags or [],
        "tailored_bullets": draft.tailored_bullets or [],
        "cover_letter": draft.cover_letter or "",
        "form_answers": draft.form_answers or {},
        "provider": draft.provider,
        "model": draft.model,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "queue_status": queue.status if queue else None,
        "queue_id": queue.id if queue else None,
        "user_notes": queue.user_notes if queue else None,
        "not_applied_reason": queue.not_applied_reason if queue else None,
    }


def open_apply_pack(
    session: Session,
    queue_id: int,
) -> dict[str, Any]:
    """Mark queue item opened and return URL + clipboard pack for assisted apply."""
    item = repo.get_queue_item(session, queue_id)
    if not item:
        raise LookupError("Queue item not found")
    draft = repo.get_draft_by_id(session, item.draft_id)
    if not draft:
        raise LookupError("Draft not found")
    job = repo.get_job_by_id(session, item.job_id)
    if item.status not in {"opened", "applied"}:
        repo.update_queue_status(session, queue_id, status="opened")
        item = repo.get_queue_item(session, queue_id) or item
    pack = build_clipboard_pack(
        draft,
        title=job.title if job else None,
        company=job.company if job else None,
        url=job.url if job else None,
    )
    data = draft_to_dict(draft, item)
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
    data["clipboard_pack"] = pack
    return data


def start_assisted_browser_fill(
    session: Session,
    config: dict[str, Any],
    queue_id: int,
) -> dict[str, Any]:
    """Launch headed Playwright fill for a queue item. Never auto-submits."""
    from api.services.agent.browser_assist import (
        BrowserAssistError,
        merge_applicant_profile,
        start_browser_assist,
    )

    item = repo.get_queue_item(session, queue_id)
    if not item:
        raise LookupError("Queue item not found")
    draft = repo.get_draft_by_id(session, item.draft_id)
    if not draft:
        raise LookupError("Draft not found")
    job = repo.get_job_by_id(session, item.job_id)
    if not job or not job.url:
        raise BrowserAssistError("Job has no apply URL")

    resume_text, _skills = _load_resume_bundle(config)
    profile = merge_applicant_profile(
        config,
        resume_text=resume_text,
        form_answers=draft.form_answers or {},
        cover_letter=draft.cover_letter or "",
    )
    if job.location and not profile.get("location"):
        profile["location"] = job.location

    status = start_browser_assist(
        queue_id=queue_id,
        url=job.url,
        profile=profile,
        config=config,
    )
    if item.status not in {"opened", "applied"}:
        repo.update_queue_status(session, queue_id, status="opened")
    return status


__all__ = [
    "analyze_run_job",
    "build_clipboard_pack",
    "draft_to_dict",
    "open_apply_pack",
    "start_assisted_browser_fill",
    "LLMError",
    "get_llm_client",
]
