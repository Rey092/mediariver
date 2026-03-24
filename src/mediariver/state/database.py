"""Database engine and session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from mediariver.state.models import Base

_DEFAULT_DB_DIR = Path.home() / ".mediariver"
_DEFAULT_DB_PATH = (_DEFAULT_DB_DIR / "state.db").resolve()
_DEFAULT_DB_URL = f"sqlite:///{_DEFAULT_DB_PATH}"


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or _DEFAULT_DB_URL
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_path = Path(url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url)


def create_tables(engine: Engine) -> None:
    """Create tables if missing, and migrate schema if needed."""
    _migrate_unique_constraint(engine)
    Base.metadata.create_all(engine)


def _migrate_unique_constraint(engine: Engine) -> None:
    """Migrate from (workflow_name, file_hash) to (workflow_name, file_path) unique constraint.

    SQLite can't ALTER constraints, so we recreate the table.
    Skipped for non-SQLite backends which handle migrations via CREATE TABLE.
    """
    if engine.dialect.name != "sqlite":
        return

    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "processed_files" not in insp.get_table_names():
        return

    # Check if already migrated
    uniques = insp.get_unique_constraints("processed_files")
    for uc in uniques:
        if set(uc["column_names"]) == {"workflow_name", "file_path"}:
            return  # already correct

    # Need migration: recreate table with new constraint
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE processed_files RENAME TO _processed_files_old"))
        conn.execute(
            text("""
            CREATE TABLE processed_files (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                workflow_name VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                file_hash VARCHAR NOT NULL,
                file_size INTEGER NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                current_step VARCHAR,
                step_results JSON NOT NULL DEFAULT '{}',
                error TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (workflow_name, file_path)
            )
        """)
        )
        conn.execute(
            text("""
            INSERT INTO processed_files
                (id, workflow_name, file_path, file_hash, file_size, status,
                 current_step, step_results, error, attempts, created_at, updated_at)
            SELECT id, workflow_name, file_path, file_hash, file_size, status,
                   current_step, step_results, error, attempts, created_at, updated_at
            FROM _processed_files_old
        """)
        )
        conn.execute(text("DROP TABLE _processed_files_old"))


def get_session(engine: Engine) -> Session:
    return Session(engine)
