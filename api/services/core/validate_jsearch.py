"""Print JSearch configuration validation (no API calls)."""

from __future__ import annotations

import json
from typing import Any

from api.services.core.fetchers.jsearch import validate_jsearch_config


def print_jsearch_validation(report: dict[str, Any]) -> None:
    print("=== JSearch configuration check (no API call) ===\n")

    if report["ok"]:
        print("OK:")
        for line in report["ok"]:
            print(f"  + {line}")
        print()

    if report["warnings"]:
        print("Warnings:")
        for line in report["warnings"]:
            print(f"  ! {line}")
        print()

    if report["issues"]:
        print("Issues (fix before calling API):")
        for line in report["issues"]:
            print(f"  x {line}")
        print()

    print("Reference curl (RapidAPI docs):")
    print(f"  {report.get('reference_curl', '')}")
    print()

    print("Side-by-side vs your config:")
    for row in report.get("curl_comparison", []):
        mark = "OK" if row["match"] else "DIFF"
        note = row.get("note", "")
        suffix = f" ({note})" if note else ""
        print(
            f"  [{mark}] {row['field']}: reference={row['reference']} | ours={row['ours']}{suffix}"
        )
    print()

    print("Our built request (1 call per run, cache-aware):")
    print(json.dumps(report["search_request"], indent=2))
    print()

    if report["valid"]:
        print(
            "Result: configuration looks correct. Safe to run: "
            "python -m api.services.core.main"
        )
        print("Tip: omit --refresh to use cache and save free-tier quota.")
    else:
        print(
            "Result: fix issues above before running "
            "python -m api.services.core.main"
        )
