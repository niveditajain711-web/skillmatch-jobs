"""JSearch (RapidAPI) fetcher."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlencode

import requests

from api.services.core.config import search_query
from api.services.core.fetchers.base import BaseFetcher, format_api_error, parse_datetime, truncate
from api.services.core.models_dto import Job

DEFAULT_HOST = "jsearch.p.rapidapi.com"
SEARCH_PATH = "search-v2"
JOB_DETAILS_PATH = "job-details"


def _jsearch_cfg(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("sources", {}).get("jsearch", {})


def _date_posted_value(posted_within: int | None) -> str:
    if not posted_within:
        return "all"
    days = int(posted_within)
    if days <= 1:
        return "today"
    if days <= 3:
        return "3days"
    if days <= 7:
        return "week"
    return "month"


def build_jsearch_headers(host: str, api_key: str) -> dict[str, str]:
    return {
        "x-rapidapi-host": host,
        "x-rapidapi-key": api_key,
    }


def build_search_request(config: dict[str, Any]) -> dict[str, Any]:
    """Build the search-v2 request our pipeline uses (no HTTP call)."""
    source_cfg = _jsearch_cfg(config)
    search_cfg = config.get("search", {})
    host = source_cfg.get("host", DEFAULT_HOST)
    search_path = source_cfg.get("search_path", SEARCH_PATH).strip("/")
    countries = search_cfg.get("countries") or []
    country = countries[0] if countries else None

    params: dict[str, Any] = {
        "query": search_query(config),
        "num_pages": int(search_cfg.get("max_pages", 1)),
        "date_posted": _date_posted_value(search_cfg.get("posted_within_days")),
    }
    if country:
        params["country"] = country
    if bool(search_cfg.get("remote_only")):
        params["remote_jobs_only"] = "true"

    api_key = source_cfg.get("_api_key") or ""
    headers = build_jsearch_headers(host, api_key)
    url = f"https://{host}/{search_path}?{urlencode(params)}"

    return {
        "purpose": "job search (used by this CLI)",
        "method": "GET",
        "endpoint": f"/{search_path}",
        "url": url,
        "headers": headers,
        "params": params,
        "api_calls_per_run": 1,
    }


def build_job_details_request(
    config: dict[str, Any],
    *,
    job_id: str,
    country: str | None = None,
) -> dict[str, Any]:
    """Build the job-details request (optional enrichment; not used by default)."""
    source_cfg = _jsearch_cfg(config)
    host = source_cfg.get("host", DEFAULT_HOST)
    details_path = source_cfg.get("job_details_path", JOB_DETAILS_PATH).strip("/")
    countries = config.get("search", {}).get("countries") or []
    resolved_country = country or (countries[0] if countries else "us")

    params = {"job_id": job_id, "country": resolved_country}
    api_key = source_cfg.get("_api_key") or ""
    headers = build_jsearch_headers(host, api_key)
    url = f"https://{host}/{details_path}?{urlencode(params)}"

    return {
        "purpose": "single job lookup (RapidAPI docs example; optional, 1 call per job)",
        "method": "GET",
        "endpoint": f"/{details_path}",
        "url": url,
        "headers": headers,
        "params": params,
        "api_calls_per_run": 1,
    }


def _mask_key(value: str) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


REFERENCE_SEARCH_V2_CURL = (
    "GET https://jsearch.p.rapidapi.com/search-v2"
    "?query=developer+jobs+in+chicago&num_pages=1&country=us&date_posted=all"
)


def extract_search_jobs(body: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    """Normalize JSearch search-v2 payloads (list or {jobs, cursor})."""
    if not body:
        return []
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict):
        jobs = body.get("jobs")
        if isinstance(jobs, list):
            return [item for item in jobs if isinstance(item, dict)]
        data = body.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            nested = data.get("jobs")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _compare_to_reference_curl(search_req: dict[str, Any]) -> list[dict[str, str]]:
    """Compare our built request to the official search-v2 curl shape."""
    ref_params = {
        "query": "developer jobs in chicago",
        "num_pages": 1,
        "country": "us",
        "date_posted": "all",
    }
    ours = search_req["params"]
    rows = [
        {
            "field": "method",
            "reference": "GET",
            "ours": search_req["method"],
            "match": search_req["method"] == "GET",
        },
        {
            "field": "endpoint",
            "reference": "/search-v2",
            "ours": search_req["endpoint"],
            "match": search_req["endpoint"] == "/search-v2",
        },
        {
            "field": "host header",
            "reference": DEFAULT_HOST,
            "ours": search_req["headers"].get("x-rapidapi-host", ""),
            "match": search_req["headers"].get("x-rapidapi-host") == DEFAULT_HOST,
        },
        {
            "field": "api key header",
            "reference": "x-rapidapi-key (set)",
            "ours": "x-rapidapi-key (set)" if search_req["headers"].get("x-rapidapi-key") else "missing",
            "match": bool(search_req["headers"].get("x-rapidapi-key")),
        },
        {
            "field": "Content-Type",
            "reference": "application/json (optional on GET)",
            "ours": "not sent (OK for GET)",
            "match": True,
        },
    ]
    for key in ("query", "num_pages", "country", "date_posted"):
        ref_val = str(ref_params.get(key, ""))
        our_val = str(ours.get(key, ""))
        rows.append(
            {
                "field": f"param:{key}",
                "reference": ref_val,
                "ours": our_val,
                "match": ref_val == our_val,
                "note": "from config.yaml" if ref_val != our_val else "",
            }
        )
    return rows


def validate_jsearch_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate JSearch setup without calling the API."""
    source_cfg = _jsearch_cfg(config)
    issues: list[str] = []
    warnings: list[str] = []
    ok: list[str] = []

    if not source_cfg.get("enabled"):
        warnings.append("JSearch is disabled in config.yaml (sources.jsearch.enabled: false).")

    api_key = source_cfg.get("_api_key")
    if not api_key:
        issues.append("RAPIDAPI_KEY is missing or still set to the placeholder in .env.")
    else:
        ok.append(f"RAPIDAPI_KEY is set ({_mask_key(api_key)}).")

    host = source_cfg.get("host", DEFAULT_HOST)
    if host != DEFAULT_HOST:
        warnings.append(f"Non-default host configured: {host}")
    else:
        ok.append(f"Host is correct: {host}")

    search_path = source_cfg.get("search_path", SEARCH_PATH).strip("/")
    if search_path != SEARCH_PATH:
        warnings.append(
            f"search_path is '{search_path}'; JSearch docs recommend '{SEARCH_PATH}' for search."
        )
    else:
        ok.append(f"Search endpoint is correct: GET /{SEARCH_PATH}")

    ok.append("This CLI uses /search-v2 for listing jobs (1 API call per run with cache).")

    search_req = build_search_request(config)
    example_details = build_job_details_request(
        config,
        job_id="qIsPjUMr0Em0hqHoAAAAAA==",
        country=(config.get("search", {}).get("countries") or ["us"])[0],
    )

    masked_search = {
        **search_req,
        "headers": {
            **search_req["headers"],
            "x-rapidapi-key": _mask_key(search_req["headers"]["x-rapidapi-key"]),
        },
    }
    masked_details = {
        **example_details,
        "headers": {
            **example_details["headers"],
            "x-rapidapi-key": _mask_key(example_details["headers"]["x-rapidapi-key"]),
        },
    }

    if search_req["params"].get("query") == "software engineer":
        warnings.append("Search query fell back to default; check search.keywords in config.")

    curl_comparison = _compare_to_reference_curl(search_req)
    structure_ok = all(
        row["match"] for row in curl_comparison if not row["field"].startswith("param:")
    )
    if structure_ok:
        ok.append("Request shape matches the official search-v2 curl (method, endpoint, headers).")
    else:
        issues.append("Request shape does not match the official search-v2 curl.")

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "ok": ok,
        "reference_curl": REFERENCE_SEARCH_V2_CURL,
        "curl_comparison": curl_comparison,
        "search_request": masked_search,
        "job_details_example": masked_details,
    }


class JSearchFetcher(BaseFetcher):
    name = "jsearch"

    def fetch(self) -> list[Job]:
        source_cfg = _jsearch_cfg(self.config)
        api_key = source_cfg.get("_api_key")
        if not api_key:
            print("Skipping jsearch: RAPIDAPI_KEY not set.")
            return []

        search_cfg = self.config.get("search", {})
        max_results = int(search_cfg.get("max_results_per_source", 30))
        req = build_search_request(self.config)
        host = source_cfg.get("host", DEFAULT_HOST)
        search_path = source_cfg.get("search_path", SEARCH_PATH).strip("/")
        headers = build_jsearch_headers(host, api_key)
        params = req["params"]

        jobs: list[Job] = []
        combined_raw: list[dict[str, Any]] = []

        def _do_fetch(p=params):
            url = f"https://{host}/{search_path}"
            resp = requests.get(url, headers=headers, params=p, timeout=45)
            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                hint = ""
                if resp.status_code in {403, 405}:
                    hint = (
                        " Subscribe to JSearch on RapidAPI (Pricing → Basic/Free) "
                        "and ensure RAPIDAPI_KEY matches that app."
                    )
                raise requests.HTTPError(
                    f"{format_api_error(exc)}.{hint}",
                    response=resp,
                ) from exc
            return resp.json()

        body = self._load_or_fetch_json(params, _do_fetch)
        if isinstance(body, dict):
            combined_raw.append(body)
            data = extract_search_jobs(body.get("data"))
        else:
            data = []

        for item in data:
            job = self._to_job(item)
            if job:
                jobs.append(job)
            if len(jobs) >= max_results:
                break

        self.last_raw_body = {"pages": combined_raw} if combined_raw else self.last_raw_body
        return jobs[:max_results]

    def _to_job(self, item: dict[str, Any]) -> Job | None:
        job_id = str(
            item.get("job_uid")
            or item.get("job_id")
            or item.get("job_apply_link")
            or ""
        )
        if len(job_id) > 255:
            job_id = hashlib.sha256(job_id.encode()).hexdigest()
        title = (item.get("job_title") or "").strip()
        if not job_id or not title:
            return None
        description = item.get("job_description") or ""
        if not description and isinstance(item.get("job_highlights"), dict):
            parts = []
            for key, vals in item["job_highlights"].items():
                if isinstance(vals, list):
                    parts.append(f"{key}: " + "; ".join(str(v) for v in vals))
            description = "\n".join(parts)
        description = truncate(str(description))

        location_parts = [
            item.get("job_city"),
            item.get("job_state"),
            item.get("job_country"),
        ]
        location = ", ".join(p for p in location_parts if p) or (item.get("job_location") or "")
        return Job(
            source=self.name,
            external_id=job_id,
            title=title,
            company=(item.get("employer_name") or "").strip(),
            location=location,
            url=(item.get("job_apply_link") or item.get("job_google_link") or "").strip(),
            description=description,
            posted_at=parse_datetime(
                item.get("job_posted_at_datetime_utc") or item.get("job_posted_at_timestamp")
            ),
            is_remote=bool(item.get("job_is_remote")) if item.get("job_is_remote") is not None else None,
            raw_json=item,
        )
