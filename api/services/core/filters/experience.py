"""Filter jobs by years-of-experience requirements parsed from title/description."""

from __future__ import annotations

import re
from typing import Any

from api.services.core.models_dto import Job

# "5+ years", "5 years+", "minimum 5 years", "at least 5 years of experience"
_MIN_PATTERNS = [
    re.compile(
        r"(?:min(?:imum)?|at\s+least|over|more\s+than)\s+(\d{1,2})\+?\s*"
        r"(?:\+?\s*)?(?:years?|yrs?)\b",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,2})\s*(?:years?|yrs?)\s*\+",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,2})\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?)\b",
        re.I,
    ),
]

# "3-5 years", "3 – 5 yrs", "3 to 5 years"
_RANGE_PATTERN = re.compile(
    r"\b(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b",
    re.I,
)

# "up to 5 years", "maximum 8 years"
_MAX_PATTERNS = [
    re.compile(
        r"(?:up\s+to|max(?:imum)?|no\s+more\s+than)\s+(\d{1,2})\s*(?:years?|yrs?)\b",
        re.I,
    ),
]


def _job_text(job: Job) -> str:
    return f"{job.title or ''}\n{job.description or ''}"


def extract_experience_range(text: str) -> tuple[float | None, float | None]:
    """
    Return (min_years, max_years) required by the posting, when detectable.
    Open-ended mins use max=None (e.g. 5+ years → (5, None)).
    """
    if not text:
        return None, None

    range_match = _RANGE_PATTERN.search(text)
    if range_match:
        a, b = int(range_match.group(1)), int(range_match.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        if hi <= 40:
            return float(lo), float(hi)

    for pat in _MAX_PATTERNS:
        m = pat.search(text)
        if m:
            years = int(m.group(1))
            if years <= 40:
                return None, float(years)

    for pat in _MIN_PATTERNS:
        m = pat.search(text)
        if m:
            years = int(m.group(1))
            if years <= 40:
                return float(years), None

    # Seniority hints when no numeric YOE is present — keep bands wide enough
    # that a mid-level candidate (e.g. 5 YOE) is not wiped by Staff labels alone.
    lower = text.lower()
    if re.search(r"\b(intern|internship|entry[\s-]?level|junior|graduate|fresher)\b", lower):
        return 0.0, 2.0
    if re.search(r"\b(principal|distinguished|fellow)\b", lower):
        return 8.0, None
    if re.search(r"\bstaff\b", lower):
        return 6.0, None
    if re.search(r"\b(senior|sr\.?)\b", lower):
        return 4.0, None
    if re.search(r"\b(mid[\s-]?level|intermediate)\b", lower):
        return 3.0, 7.0

    return None, None


def _candidate_fits(
    yoe: float,
    req_min: float | None,
    req_max: float | None,
    *,
    tolerance: float = 1.0,
) -> bool:
    """
    Keep job if candidate YOE is compatible with the posting.
    tolerance: allow being slightly under a min or over a max (common for ranges).
    """
    if req_min is None and req_max is None:
        return True
    if req_min is not None and yoe + tolerance < req_min:
        return False
    if req_max is not None and yoe - tolerance > req_max:
        return False
    return True


def filter_jobs_by_experience(
    jobs: list[Job],
    *,
    years_of_experience: float | None = None,
    experience_min: float | None = None,
    experience_max: float | None = None,
    keep_unknown: bool = True,
    tolerance: float = 1.0,
) -> list[Job]:
    """
    Filter jobs by experience.

    Preferred: set years_of_experience to *your* YOE — jobs whose required
    band is incompatible are dropped.

    Optional experience_min / experience_max further constrain which job
    requirement bands you want to see (e.g. skip 0–2 junior roles).
    """
    if years_of_experience is None and experience_min is None and experience_max is None:
        return jobs

    kept: list[Job] = []
    for job in jobs:
        req_min, req_max = extract_experience_range(_job_text(job))
        unknown = req_min is None and req_max is None
        if unknown:
            if keep_unknown:
                kept.append(job)
            continue

        # Candidate YOE must fit the job's asked range
        if years_of_experience is not None:
            if not _candidate_fits(
                float(years_of_experience),
                req_min,
                req_max,
                tolerance=tolerance,
            ):
                continue

        # Optional: only keep jobs whose requirement overlaps your preferred band
        if experience_min is not None and req_max is not None and req_max < experience_min:
            continue
        if experience_max is not None and req_min is not None and req_min > experience_max:
            continue

        kept.append(job)
    return kept


def experience_filter_from_config(config: dict[str, Any]) -> dict[str, Any]:
    search = config.get("search", {}) or {}
    yoe = search.get("years_of_experience")
    exp_min = search.get("experience_min")
    exp_max = search.get("experience_max")
    keep_unknown = search.get("keep_unknown_experience", True)
    tolerance = search.get("experience_tolerance", 1.0)
    return {
        "years_of_experience": float(yoe) if yoe is not None and yoe != "" else None,
        "experience_min": float(exp_min) if exp_min is not None and exp_min != "" else None,
        "experience_max": float(exp_max) if exp_max is not None and exp_max != "" else None,
        "keep_unknown": bool(keep_unknown),
        "tolerance": float(tolerance) if tolerance is not None else 1.0,
    }
