"""Post-fetch country filtering for sources that ignore country params."""

from __future__ import annotations

import re

from api.services.core.models_dto import Job

# ISO country code -> location terms to match in job text
COUNTRY_TERMS: dict[str, list[str]] = {
    "in": [
        "india",
        "indian",
        "bangalore",
        "bengaluru",
        "mumbai",
        "pune",
        "hyderabad",
        "delhi",
        "new delhi",
        "gurgaon",
        "gurugram",
        "noida",
        "chennai",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "kochi",
        "indore",
        "lucknow",
        "nagpur",
        "remote india",
        "work from india",
        "based in india",
    ],
    "us": [
        "united states",
        "usa",
        "u.s.",
        "america",
        "new york",
        "san francisco",
        "california",
        "texas",
        "seattle",
        "boston",
        "chicago",
        "remote us",
        "remote usa",
    ],
    "gb": ["united kingdom", "uk", "london", "england", "scotland", "remote uk"],
    "de": ["germany", "berlin", "munich", "frankfurt", "deutschland"],
    "ca": ["canada", "toronto", "vancouver", "montreal", "remote canada"],
    "au": ["australia", "sydney", "melbourne", "remote australia"],
}

# Locations that mean "any country" — excluded when filtering for a specific country
WORLDWIDE_MARKERS = (
    "worldwide",
    "world-wide",
    "anywhere",
    "any country",
    "global",
    "international",
    "emea",
    "apac",
    "europe",
    "latin america",
)


def _job_blob(job: Job) -> str:
    parts = [
        job.location or "",
        job.title or "",
        job.company or "",
        (job.description or "")[:2000],
    ]
    return re.sub(r"\s+", " ", " ".join(parts).lower())


def _matches_country(blob: str, country_code: str) -> bool:
    code = country_code.lower().strip()
    terms = COUNTRY_TERMS.get(code, [code])
    if any(term in blob for term in terms):
        return True
    # Bare code as word boundary (e.g. " IN " in location) — risky for "in" as preposition
    if len(code) > 2 and re.search(rf"(?<![a-z]){re.escape(code)}(?![a-z])", blob):
        return True
    return False


def filter_jobs_by_country(
    jobs: list[Job],
    countries: list[str],
    *,
    skip_sources: set[str] | None = None,
) -> list[Job]:
    """
    Keep jobs tied to configured countries.
    Sources in skip_sources (e.g. jsearch) are already country-filtered by their API.
    """
    codes = [c.lower().strip() for c in countries if c and str(c).strip()]
    if not codes:
        return jobs

    skip = {s.lower() for s in (skip_sources or set())}
    filtered: list[Job] = []
    for job in jobs:
        if job.source.lower() in skip:
            filtered.append(job)
            continue

        blob = _job_blob(job)
        loc = (job.location or "").lower().strip()

        if loc and any(marker in loc for marker in WORLDWIDE_MARKERS):
            if not any(_matches_country(blob, code) for code in codes):
                continue

        if any(_matches_country(blob, code) for code in codes):
            filtered.append(job)

    return filtered
