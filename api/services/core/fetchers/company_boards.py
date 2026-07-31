"""Curated company career-board fetchers (Greenhouse, Lever, Ashby, Workday).

These hit official / ATS public APIs for companies you list in config.yaml.
They do not cover the whole market — only the boards you curate.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from api.services.core.fetchers.base import BaseFetcher, parse_datetime, truncate
from api.services.core.models_dto import Job

USER_AGENT = "SkillMatchJobs/0.1 (+local personal job search)"


def _keywords(config: dict[str, Any]) -> list[str]:
    return [str(k).lower().strip() for k in (config.get("search", {}).get("keywords") or []) if str(k).strip()]


def _matches_keywords(title: str, description: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    blob = f"{title}\n{description}".lower()
    # Prefer title hits; description helps when include_descriptions is enabled.
    return any(k in blob for k in keywords)


def _company_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = config.get("sources", {}).get("company_boards", {})
    companies = cfg.get("companies") or []
    return [c for c in companies if isinstance(c, dict) and c.get("board") and c.get("token")]


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text or "")
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class CompanyBoardsFetcher(BaseFetcher):
    """Fetch open roles from curated Greenhouse / Lever / Ashby / Workday boards."""

    name = "company_boards"

    def fetch(self) -> list[Job]:
        entries = _company_entries(self.config)
        if not entries:
            print("Skipping company_boards: no companies configured.")
            return []

        search_cfg = self.config.get("search", {})
        board_cfg = self.config.get("sources", {}).get("company_boards", {})
        max_results = int(
            board_cfg.get("max_results")
            or search_cfg.get("max_results_per_source")
            or 100
        )
        keywords = _keywords(self.config)
        remote_only = bool(search_cfg.get("remote_only"))
        filter_keywords = bool(board_cfg.get("keyword_filter", True))
        workers = int(board_cfg.get("parallel_workers") or 12)

        all_jobs: list[Job] = []
        raw_pages: list[dict[str, Any]] = []

        def _one(entry: dict[str, Any]) -> tuple[str, str, str, list[Job], str | None]:
            board = str(entry.get("board", "")).lower().strip()
            token = str(entry.get("token", "")).strip()
            company_name = str(entry.get("name") or token).strip()
            try:
                jobs, _raw = self._fetch_board(board, token, company_name, entry)
                return company_name, board, token, jobs, None
            except Exception as exc:  # noqa: BLE001
                return company_name, board, token, [], str(exc)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(_one, entry) for entry in entries]
            for fut in as_completed(futures):
                company_name, board, token, jobs, err = fut.result()
                if err:
                    print(f"[company_boards] {company_name} ({board}/{token}) error: {err}")
                    raw_pages.append(
                        {
                            "board": board,
                            "token": token,
                            "name": company_name,
                            "count": 0,
                            "error": err,
                        }
                    )
                    continue

                raw_pages.append(
                    {
                        "board": board,
                        "token": token,
                        "name": company_name,
                        "count": len(jobs),
                    }
                )
                for job in jobs:
                    if filter_keywords and not _matches_keywords(
                        job.title, job.description, keywords
                    ):
                        continue
                    if remote_only and job.is_remote is False:
                        continue
                    all_jobs.append(job)

        # Prefer title keyword matches first, then keep max_results
        if filter_keywords and keywords:
            title_hits = [
                j for j in all_jobs if any(k in j.title.lower() for k in keywords)
            ]
            title_ids = {id(j) for j in title_hits}
            rest = [j for j in all_jobs if id(j) not in title_ids]
            all_jobs = title_hits + rest

        params = {
            "boards": [f"{e.get('board')}:{e.get('token')}" for e in entries],
            "keywords": keywords,
            "remote_only": remote_only,
        }
        self.last_request_params = params
        self.last_raw_body = {
            "boards": sorted(raw_pages, key=lambda r: r.get("name") or ""),
            "matched": len(all_jobs),
        }
        self.last_cache_key = None
        self.used_cache = False
        print(
            f"[company_boards] scanned {len(entries)} companies, "
            f"matched {len(all_jobs)} (keeping {min(len(all_jobs), max_results)})"
        )
        return all_jobs[:max_results]

    def _fetch_board(
        self,
        board: str,
        token: str,
        company_name: str,
        entry: dict[str, Any],
    ) -> tuple[list[Job], Any]:
        if board == "greenhouse":
            return self._fetch_greenhouse(token, company_name)
        if board == "lever":
            return self._fetch_lever(token, company_name)
        if board == "ashby":
            return self._fetch_ashby(token, company_name)
        if board == "workday":
            return self._fetch_workday(token, company_name, entry)
        raise ValueError(f"Unsupported board type: {board}")

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}

    def _fetch_greenhouse(self, token: str, company_name: str) -> tuple[list[Job], Any]:
        # Skip HTML content by default — much faster for large curated lists.
        include_content = bool(
            self.config.get("sources", {})
            .get("company_boards", {})
            .get("include_descriptions", False)
        )
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        params = {"content": "true"} if include_content else {}
        resp = requests.get(url, params=params, headers=self._headers(), timeout=45)
        resp.raise_for_status()
        body = resp.json()
        jobs: list[Job] = []
        for item in body.get("jobs") or []:
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("id") or "")
            title = (item.get("title") or "").strip()
            if not job_id or not title:
                continue
            loc = ""
            if isinstance(item.get("location"), dict):
                loc = (item["location"].get("name") or "").strip()
            absolute = (item.get("absolute_url") or "").strip()
            desc = _strip_html(item.get("content") or "") if include_content else ""
            jobs.append(
                Job(
                    source=self.name,
                    external_id=f"gh:{token}:{job_id}",
                    title=title,
                    company=company_name,
                    location=loc,
                    url=absolute,
                    description=truncate(desc),
                    posted_at=parse_datetime(item.get("updated_at") or item.get("created_at")),
                    is_remote=_infer_remote(title, loc, desc),
                    raw_json={"board": "greenhouse", "token": token, "id": item.get("id"), "title": title},
                )
            )
        return jobs, {"jobs_count": len(jobs)}

    def _fetch_lever(self, token: str, company_name: str) -> tuple[list[Job], Any]:
        url = f"https://api.lever.co/v0/postings/{token}"
        resp = requests.get(url, params={"mode": "json"}, headers=self._headers(), timeout=45)
        resp.raise_for_status()
        body = resp.json()
        items = body if isinstance(body, list) else body.get("data") or []
        jobs: list[Job] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("id") or "")
            title = (item.get("text") or "").strip()
            if not job_id or not title:
                continue
            cats = item.get("categories") or {}
            loc = ""
            if isinstance(cats, dict):
                loc = (cats.get("location") or "").strip()
            desc_parts = []
            for key in ("descriptionPlain", "description", "additionalPlain", "additional"):
                val = item.get(key)
                if val:
                    desc_parts.append(_strip_html(str(val)))
            desc = "\n".join(desc_parts)
            apply_url = (item.get("hostedUrl") or item.get("applyUrl") or "").strip()
            jobs.append(
                Job(
                    source=self.name,
                    external_id=f"lever:{token}:{job_id}",
                    title=title,
                    company=company_name,
                    location=loc,
                    url=apply_url,
                    description=truncate(desc),
                    posted_at=parse_datetime(
                        (item.get("createdAt") / 1000)
                        if isinstance(item.get("createdAt"), (int, float))
                        else item.get("createdAt")
                    ),
                    is_remote=_infer_remote(title, loc, desc)
                    or bool(item.get("workplaceType") == "remote"),
                    raw_json={"board": "lever", "token": token, **item},
                )
            )
        return jobs, body

    def _fetch_ashby(self, token: str, company_name: str) -> tuple[list[Job], Any]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        resp = requests.get(
            url,
            params={"includeCompensation": "true"},
            headers=self._headers(),
            timeout=45,
        )
        resp.raise_for_status()
        body = resp.json()
        jobs: list[Job] = []
        for item in body.get("jobs") or []:
            if not isinstance(item, dict):
                continue
            if item.get("isListed") is False:
                continue
            job_id = str(item.get("id") or item.get("jobUrl") or "")
            title = (item.get("title") or "").strip()
            if not job_id or not title:
                continue
            loc = (item.get("location") or "").strip()
            secondary = item.get("secondaryLocations") or []
            if isinstance(secondary, list) and secondary:
                extra = [
                    (s.get("location") if isinstance(s, dict) else str(s))
                    for s in secondary
                ]
                extra_s = ", ".join(x for x in extra if x)
                if extra_s:
                    loc = f"{loc}; {extra_s}" if loc else extra_s
            desc = item.get("descriptionPlain") or _strip_html(item.get("descriptionHtml") or "")
            apply_url = (item.get("applyUrl") or item.get("jobUrl") or "").strip()
            is_remote = item.get("isRemote")
            if is_remote is None:
                is_remote = _infer_remote(title, loc, str(desc))
            jobs.append(
                Job(
                    source=self.name,
                    external_id=f"ashby:{token}:{job_id}",
                    title=title,
                    company=company_name,
                    location=loc,
                    url=apply_url,
                    description=truncate(str(desc)),
                    posted_at=parse_datetime(item.get("publishedAt")),
                    is_remote=bool(is_remote) if is_remote is not None else None,
                    raw_json={"board": "ashby", "token": token, **item},
                )
            )
        return jobs, body

    def _fetch_workday(
        self,
        token: str,
        company_name: str,
        entry: dict[str, Any],
    ) -> tuple[list[Job], Any]:
        """
        Workday public CXS search.

        Config example:
          board: workday
          token: acme          # tenant
          site: External      # careers site path segment
          host: acme.wd5.myworkdayjobs.com   # optional override
        """
        site = str(entry.get("site") or "External").strip()
        host = str(entry.get("host") or f"{token}.wd5.myworkdayjobs.com").strip()
        search_text = " ".join(_keywords(self.config))
        url = f"https://{host}/wday/cxs/{token}/{site}/jobs"
        payload = {
            "appliedFacets": {},
            "limit": int(entry.get("limit") or 50),
            "offset": 0,
            "searchText": search_text,
        }
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=45)
        resp.raise_for_status()
        body = resp.json()
        jobs: list[Job] = []
        for item in body.get("jobPostings") or []:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            path = (item.get("externalPath") or "").strip()
            if not title or not path:
                continue
            job_id = path.rstrip("/").split("/")[-1] or path
            loc = (item.get("locationsText") or "").strip()
            apply_url = f"https://{host}/{site}{path}"
            jobs.append(
                Job(
                    source=self.name,
                    external_id=f"wd:{token}:{job_id}"[:255],
                    title=title,
                    company=company_name,
                    location=loc,
                    url=apply_url,
                    description=truncate(item.get("bulletFields") and " · ".join(item["bulletFields"]) or ""),
                    posted_at=parse_datetime(item.get("postedOn") or item.get("published")),
                    is_remote=_infer_remote(title, loc, ""),
                    raw_json={"board": "workday", "token": token, "site": site, **item},
                )
            )
        return jobs, body


def _infer_remote(title: str, location: str, description: str) -> bool | None:
    blob = f"{title} {location} {description}".lower()
    if any(x in blob for x in ("remote", "work from home", "wfh", "anywhere")):
        return True
    if any(x in blob for x in ("onsite", "on-site", "in office", "hybrid")):
        # hybrid is not fully remote
        if "hybrid" in blob and "remote" not in blob:
            return False
        if "remote" not in blob:
            return False
    return None
