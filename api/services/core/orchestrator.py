"""End-to-end search → score → persist → report pipeline."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from api.services.core.config import search_query
from api.services.core.db import init_db, session_scope
from api.services.core.db import repository as repo
from api.services.core.fetchers import (
    ArbeitnowFetcher,
    CompanyBoardsFetcher,
    JSearchFetcher,
    RemotiveFetcher,
    ResponseCache,
)
from api.services.core.fetchers.base import BaseFetcher, format_api_error
from api.services.core.filters.country import filter_jobs_by_country
from api.services.core.filters.experience import (
    experience_filter_from_config,
    filter_jobs_by_experience,
)
from api.services.core.models_dto import Job, ScoredJob
from api.services.core.parsing.resume import load_resume
from api.services.core.reporting.excel import write_excel_report
from api.services.core.scoring.matcher import score_jobs


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip().lower())
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def dedupe_jobs(jobs: list[Job]) -> list[Job]:
    seen_ids: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    seen_title_company: set[str] = set()
    unique: list[Job] = []

    for job in jobs:
        src_key = (job.source, job.external_id)
        if src_key in seen_ids:
            continue
        url_key = _normalize_url(job.url)
        if url_key and url_key in seen_urls:
            continue
        tc = f"{_normalize_key(job.company)}::{_normalize_key(job.title)}"
        if tc != "::" and tc in seen_title_company:
            continue

        seen_ids.add(src_key)
        if url_key:
            seen_urls.add(url_key)
        if tc != "::":
            seen_title_company.add(tc)
        unique.append(job)
    return unique


def _build_fetchers(
    config: dict[str, Any],
    cache: ResponseCache,
    refresh: bool,
) -> list[BaseFetcher]:
    sources = config.get("sources", {})
    fetchers: list[BaseFetcher] = []
    if sources.get("jsearch", {}).get("enabled"):
        fetchers.append(JSearchFetcher(config, cache, refresh=refresh))
    if sources.get("remotive", {}).get("enabled"):
        fetchers.append(RemotiveFetcher(config, cache, refresh=refresh))
    if sources.get("arbeitnow", {}).get("enabled"):
        fetchers.append(ArbeitnowFetcher(config, cache, refresh=refresh))
    if sources.get("company_boards", {}).get("enabled"):
        fetchers.append(CompanyBoardsFetcher(config, cache, refresh=refresh))
    return fetchers


def run_pipeline(
    config: dict[str, Any],
    *,
    refresh: bool = False,
    rescore_only: bool = False,
) -> dict[str, Any]:
    init_db(config["database"]["url"])

    resume_cfg = config.get("resume", {})
    resume = load_resume(
        resume_cfg.get("path", "./data/resume.pdf"),
        resume_cfg.get("text_fallback_path", "./data/resume.txt"),
    )
    keywords = search_query(config)
    mode = "rescore-only" if rescore_only else ("refresh" if refresh else "normal")

    print(f"Resume loaded from: {resume.source_path}")
    print(f"Detected skills ({len(resume.skills)}): {', '.join(resume.skills) or '(none)'}")
    print(f"Mode: {mode}")

    jobs: list[Job] = []
    sources_used: list[str] = []
    fetcher_meta: list[dict[str, Any]] = []

    cache_cfg = config.get("cache", {})
    cache = ResponseCache(
        cache_dir=cache_cfg.get("dir", "./cache"),
        ttl_hours=int(cache_cfg.get("ttl_hours", 24)),
        enabled=bool(cache_cfg.get("enabled", True)) and not refresh,
    )

    with session_scope() as session:
        run = repo.create_search_run(
            session,
            keywords=keywords,
            config=config,
            resume_path=resume.source_path,
            resume_skills=resume.skills,
        )
        run_id = run.id

        try:
            if rescore_only:
                jobs = repo.load_recent_jobs(session, limit=500)
                sources_used = sorted({j.source for j in jobs})
                print(f"Loaded {len(jobs)} jobs from database for rescoring.")
            else:
                for fetcher in _build_fetchers(config, cache, refresh=refresh):
                    try:
                        batch = fetcher.fetch()
                        print(
                            f"[{fetcher.name}] fetched {len(batch)} jobs "
                            f"(cache={'hit' if fetcher.used_cache else 'miss'})"
                        )
                        if fetcher.last_raw_body is not None:
                            repo.save_raw_response(
                                session,
                                search_run_id=run.id,
                                source=fetcher.name,
                                request_params=fetcher.last_request_params,
                                response_body=fetcher.last_raw_body,
                                cache_key=fetcher.last_cache_key,
                            )
                        jobs.extend(batch)
                        sources_used.append(fetcher.name)
                        fetcher_meta.append(
                            {
                                "source": fetcher.name,
                                "count": len(batch),
                                "cache_hit": fetcher.used_cache,
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"[{fetcher.name}] error: {format_api_error(exc)}")

            jobs = dedupe_jobs(jobs)
            print(f"Jobs after dedupe: {len(jobs)}")

            search_cfg = config.get("search", {})
            countries = search_cfg.get("countries") or []
            strict_country = search_cfg.get("strict_country_filter", True)
            if countries and strict_country:
                before = len(jobs)
                jobs = filter_jobs_by_country(
                    jobs, countries, skip_sources={"jsearch"}
                )
                removed = before - len(jobs)
                print(
                    f"Jobs after country filter ({', '.join(countries)}): "
                    f"{len(jobs)} (removed {removed})"
                )
                if before > 0 and len(jobs) == 0:
                    print(
                        "Warning: country filter removed all jobs. "
                        "Enable JSearch for India-specific results, or set "
                        "strict_country_filter: false in config.yaml."
                    )

            exp_opts = experience_filter_from_config(config)
            if (
                exp_opts["years_of_experience"] is not None
                or exp_opts["experience_min"] is not None
                or exp_opts["experience_max"] is not None
            ):
                before = len(jobs)
                jobs = filter_jobs_by_experience(jobs, **exp_opts)
                print(
                    f"Jobs after experience filter "
                    f"(yoe={exp_opts['years_of_experience']}, "
                    f"min={exp_opts['experience_min']}, "
                    f"max={exp_opts['experience_max']}): "
                    f"{len(jobs)} (removed {before - len(jobs)})"
                )

            scored: list[ScoredJob] = score_jobs(
                jobs, resume.skills, config.get("scoring", {})
            )
            print(f"Jobs scored (after min threshold): {len(scored)}")

            repo.save_scores(session, run.id, scored)

            report_cfg = config.get("report", {})
            report_path = write_excel_report(
                scored,
                output_dir=report_cfg.get("output_dir", "./reports"),
                filename_prefix=report_cfg.get("filename_prefix", "job_matches"),
                keywords=keywords,
                resume_skills=resume.skills,
                meta={
                    "jobs_fetched": len(jobs),
                    "sources_used": ", ".join(sources_used),
                    "mode": mode,
                },
            )
            print(f"Excel report: {report_path}")

            repo.finish_search_run(
                session,
                run,
                status="completed",
                jobs_fetched=len(jobs),
                jobs_scored=len(scored),
                report_path=str(report_path),
            )

            top = scored[:5]
            if top:
                print("\nTop matches:")
                for item in top:
                    print(
                        f"  {item.score:6.2f} | {item.job.title} @ {item.job.company} "
                        f"[{item.job.source}]"
                    )

            return {
                "search_run_id": run.id,
                "jobs_fetched": len(jobs),
                "jobs_scored": len(scored),
                "report_path": str(report_path),
                "sources_used": sources_used,
                "fetcher_meta": fetcher_meta,
            }
        except Exception as exc:
            repo.finish_search_run(
                session,
                run,
                status="failed",
                jobs_fetched=len(jobs),
                jobs_scored=0,
                report_path=None,
            )
            raise RuntimeError(str(exc)) from exc