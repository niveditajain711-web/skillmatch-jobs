"""Resume-vs-job keyword scoring."""

from __future__ import annotations

from typing import Any

from api.services.core.models_dto import Job, ScoredJob
from api.services.core.parsing.skills import extract_skills_from_text, split_job_skill_buckets, title_skill_overlap


def _ratio(matched: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return matched / total


def score_job(
    job: Job,
    resume_skills: list[str],
    scoring_cfg: dict[str, Any] | None = None,
) -> ScoredJob:
    cfg = scoring_cfg or {}
    must_w = float(cfg.get("must_have_weight", 0.6))
    nice_w = float(cfg.get("nice_to_have_weight", 0.3))
    title_w = float(cfg.get("title_weight", 0.1))
    total_w = must_w + nice_w + title_w
    if total_w <= 0:
        must_w, nice_w, title_w, total_w = 0.6, 0.3, 0.1, 1.0

    resume_set = set(resume_skills)
    must, nice = split_job_skill_buckets(job.description or "")

    # If description yielded nothing, try title + company blob lightly
    if not must and not nice:
        must, nice = split_job_skill_buckets(f"{job.title}\n{job.description}")

    must_matched = sorted(s for s in must if s in resume_set)
    must_missing = sorted(s for s in must if s not in resume_set)
    nice_matched = sorted(s for s in nice if s in resume_set)
    nice_missing = sorted(s for s in nice if s not in resume_set)

    must_score = _ratio(len(must_matched), len(must)) if must else 0.0
    nice_score = _ratio(len(nice_matched), len(nice)) if nice else 0.0

    # If no structured buckets, score against all skills found in the description.
    if not must and not nice:
        all_skills = extract_skills_from_text(job.description or "")
        if all_skills:
            matched_all = [s for s in all_skills if s in resume_set]
            must_score = _ratio(len(matched_all), len(all_skills))
        else:
            must_score = 0.0

    title_score = title_skill_overlap(job.title or "", resume_skills)

    score = 100.0 * (
        (must_w * must_score) + (nice_w * nice_score) + (title_w * title_score)
    ) / total_w

    matched = sorted(set(must_matched + nice_matched))
    missing = sorted(set(must_missing + nice_missing))

    return ScoredJob(
        job=job,
        score=round(score, 2),
        matched_keywords=matched,
        missing_keywords=missing,
        title_match=round(title_score * 100.0, 2),
    )


def score_jobs(
    jobs: list[Job],
    resume_skills: list[str],
    scoring_cfg: dict[str, Any] | None = None,
) -> list[ScoredJob]:
    scored = [score_job(job, resume_skills, scoring_cfg) for job in jobs]
    min_score = float((scoring_cfg or {}).get("min_score_to_save", 0) or 0)
    filtered = [s for s in scored if s.score >= min_score]
    return sorted(filtered, key=lambda s: s.score, reverse=True)