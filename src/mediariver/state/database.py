"""Database engine and session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from mediariver.state.models import Base

_DEFAULT_DB_DIR = Path.home() / ".mediariver"
_DEFAULT_DB_URL = f"sqlite:///{_DEFAULT_DB_DIR}/state.db"


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or _DEFAULT_DB_URL
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_path = Path(url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url)


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    return Session(engine)
