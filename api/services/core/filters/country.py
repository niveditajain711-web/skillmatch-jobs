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
        "coimbatore",
        "chandigarh",
        "thiruvananthapuram",
        "trivandrum",
        "mysore",
        "mysuru",
        "remote india",
        "work from india",
        "based in india",
        "india remote",
        "pan india",
        "pan-india",
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

# Locations that mean "any country"
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
    "work from anywhere",
    "remote worldwide",
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
    # Bare ISO code as standalone token (avoid matching English "in")
    if len(code) == 2 and code != "in":
        if re.search(rf"(?<![a-z]){re.escape(code)}(?![a-z])", blob):
            return True
    elif len(code) > 2:
        if re.search(rf"(?<![a-z]){re.escape(code)}(?![a-z])", blob):
            return True
    # India: allow ", IN" / " IN," style location suffixes
    if code == "in" and re.search(r"(?<![a-z])in(?![a-z])", blob):
        # Only if paired with city-like punctuation (Bangalore, IN) or standalone country
        if re.search(r",\s*in\b|\bin\s*$|\blocation:\s*in\b", blob):
            return True
    return False


def _is_remote_friendly(job: Job, blob: str) -> bool:
    if job.is_remote is True:
        return True
    loc = (job.location or "").lower()
    if any(m in loc for m in WORLDWIDE_MARKERS):
        return True
    if "remote" in loc or "work from anywhere" in blob or "remote-friendly" in blob:
        return True
    return False


def filter_jobs_by_country(
    jobs: list[Job],
    countries: list[str],
    *,
    skip_sources: set[str] | None = None,
    keep_remote_worldwide: bool = True,
    keep_unknown_location: bool = True,
) -> list[Job]:
    """
    Keep jobs tied to configured countries.

    Sources in skip_sources (e.g. jsearch) are already country-filtered by their API.

    keep_remote_worldwide: also keep remote / worldwide roles (common for India seekers).
    keep_unknown_location: keep jobs with no location text (esp. ATS boards).
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

        if any(_matches_country(blob, code) for code in codes):
            filtered.append(job)
            continue

        if keep_remote_worldwide and _is_remote_friendly(job, blob):
            filtered.append(job)
            continue

        if keep_unknown_location and not loc:
            filtered.append(job)
            continue

    return filtered
