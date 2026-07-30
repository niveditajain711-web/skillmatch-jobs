"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from api.services.core.config import load_config
from api.services.core.db.session import init_db, session_scope

_config: dict[str, Any] | None = None


def get_config() -> dict[str, Any]:
    global _config
    if _config is None:
        _config = load_config()
        init_db(_config["database"]["url"])
    return _config


def reload_config() -> dict[str, Any]:
    """Reload config from disk/.env (e.g. after .env changes)."""
    global _config
    _config = load_config()
    init_db(_config["database"]["url"])
    return _config


def get_db(
    _config: dict[str, Any] = Depends(get_config),
) -> Generator[Session, None, None]:
    del _config  # used only to ensure DB is initialized
    with session_scope() as session:
        yield session
