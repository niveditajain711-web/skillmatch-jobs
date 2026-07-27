"""CLI entrypoint for personal job search + resume matching."""

from __future__ import annotations

import sys
from pathlib import Path

import click

# Allow `python -m src.main` from project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.orchestrator import run_pipeline
from src.validate_jsearch import print_jsearch_validation
from src.fetchers.jsearch import validate_jsearch_config


@click.command()
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to config.yaml (default: ./config.yaml)",
)
@click.option(
    "--refresh",
    is_flag=True,
    default=False,
    help="Ignore cache and hit job APIs again.",
)
@click.option(
    "--rescore-only",
    is_flag=True,
    default=False,
    help="Skip fetching; rescore jobs already stored in Postgres.",
)
@click.option(
    "--validate-jsearch",
    is_flag=True,
    default=False,
    help="Check JSearch config and show the request that would be sent (no API call).",
)
def main(
    config_path: str | None,
    refresh: bool,
    rescore_only: bool,
    validate_jsearch: bool,
) -> None:
    """Fetch jobs, score resume match, save to Postgres + Excel."""
    if refresh and rescore_only:
        raise click.UsageError("Use either --refresh or --rescore-only, not both.")

    config = load_config(config_path)

    if validate_jsearch:
        print_jsearch_validation(validate_jsearch_config(config))
        return

    result = run_pipeline(config, refresh=refresh, rescore_only=rescore_only)
    click.echo(
        f"\nDone. run_id={result['search_run_id']} "
        f"fetched={result['jobs_fetched']} scored={result['jobs_scored']}"
    )


if __name__ == "__main__":
    main()