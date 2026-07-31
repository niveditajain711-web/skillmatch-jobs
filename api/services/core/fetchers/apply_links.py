"""Prefer official / direct apply links over aggregator boards."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

# Aggregators that often gate apply behind signup / subscription.
LOW_QUALITY_HOST_MARKERS = (
    "bebee.",
    "shine.com",
    "jobleads.",
    "jobisjob.",
    "neuvoo.",
    "jooble.",
    "adzuna.",
    "talent.com",
    "whatjobs.",
    "jobgether.",
    "appcast.",
)

# Strong signals that this is a company career / ATS apply page.
OFFICIAL_HOST_MARKERS = (
    "greenhouse.io",
    "boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "smartrecruiters.com",
    "icims.com",
    "taleo.net",
    "successfactors.",
    "oraclecloud.com",
    "careers.",
    "jobs.",
)

# Better than Shine/BeBee but still not the company site.
MID_QUALITY_HOST_MARKERS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.",
    "ziprecruiter.com",
    "monster.com",
    "dice.com",
)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _score_url(url: str, *, is_direct: bool = False, publisher: str = "") -> int:
    if not url:
        return -1000
    host = _host(url)
    pub = (publisher or "").lower()
    score = 0

    if is_direct:
        score += 50
    if any(m in host for m in OFFICIAL_HOST_MARKERS):
        score += 100
    if "career" in host or host.startswith("jobs.") or ".jobs." in host:
        score += 40
    if any(m in pub for m in ("career", "careers", "official")):
        score += 30
    if any(m in host for m in MID_QUALITY_HOST_MARKERS):
        score += 10
    if any(m in host for m in LOW_QUALITY_HOST_MARKERS):
        score -= 80
    if any(m in pub for m in ("bebee", "shine", "jobleads", "jooble", "neuvoo")):
        score -= 80
    return score


def pick_best_apply_url(
    item: dict[str, Any],
    *,
    fallback: str = "",
) -> str:
    """
    Choose the best apply URL from a JSearch (or similar) job payload.

    Prefers company ATS / careers pages over aggregator boards.
    """
    candidates: list[tuple[str, bool, str]] = []

    apply_options = item.get("apply_options")
    if isinstance(apply_options, list):
        for opt in apply_options:
            if not isinstance(opt, dict):
                continue
            link = (opt.get("apply_link") or opt.get("link") or "").strip()
            if not link:
                continue
            candidates.append(
                (
                    link,
                    bool(opt.get("is_direct")),
                    str(opt.get("publisher") or ""),
                )
            )

    primary = (item.get("job_apply_link") or "").strip()
    if primary:
        candidates.append(
            (
                primary,
                bool(item.get("job_apply_is_direct")),
                str(item.get("job_publisher") or ""),
            )
        )

    employer_site = (item.get("employer_website") or "").strip()
    if employer_site:
        # Not always an apply page, but better than Shine/BeBee as last resort context.
        candidates.append((employer_site, False, "employer_website"))

    google = (item.get("job_google_link") or "").strip()
    if google:
        candidates.append((google, False, "google"))

    if fallback:
        candidates.append((fallback, False, "fallback"))

    if not candidates:
        return ""

    best = max(
        candidates,
        key=lambda c: _score_url(c[0], is_direct=c[1], publisher=c[2]),
    )
    return best[0]
