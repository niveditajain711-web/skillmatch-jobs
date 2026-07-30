"""Load and validate application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    load_dotenv(_project_root() / ".env")
    path = Path(config_path) if config_path else _project_root() / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    db_env = config.get("database", {}).get("url_env", "DATABASE_URL")
    database_url = os.getenv(db_env)
    if not database_url:
        raise ValueError(
            f"Database URL missing. Set {db_env} in .env (see .env.example)."
        )
    config["database"]["url"] = database_url

    jsearch = config.setdefault("sources", {}).setdefault("jsearch", {})
    key_env = jsearch.get("api_key_env", "RAPIDAPI_KEY")
    api_key = os.getenv(key_env, "")
    if api_key and api_key != "your_rapidapi_key_here":
        jsearch["_api_key"] = api_key
    else:
        jsearch["_api_key"] = None

    return config


def search_query(config: dict[str, Any]) -> str:
    keywords = config.get("search", {}).get("keywords") or []
    location = (config.get("search", {}).get("location") or "").strip()
    query = " ".join(str(k) for k in keywords).strip()
    if location:
        query = f"{query} {location}".strip()
    return query or "software engineer"