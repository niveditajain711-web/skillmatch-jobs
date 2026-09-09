"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.services.core.db.models import Base

_engine = None
_SessionLocal = None


def init_db(database_url: str) -> None:
    global _engine, _SessionLocal
    _engine = create_engine(database_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    try:
        Base.metadata.create_all(bind=_engine)
        _ensure_schema_patches(_engine)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Could not connect to PostgreSQL. Update DATABASE_URL in .env "
            "(or run: docker compose up -d). Original error: "
            f"{exc}"
        ) from exc


def _ensure_schema_patches(engine) -> None:
    """Additive column patches for existing DBs (create_all does not ALTER)."""
    from sqlalchemy import text

    statements = [
        "ALTER TABLE apply_queue ADD COLUMN IF NOT EXISTS not_applied_reason VARCHAR(64)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_engine():
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()