"""Safe database generation bootstrap (old business data is never migrated)."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import select

from apiswitch import __version__
from apiswitch.config import settings
from apiswitch.db.base import Base, utc_now
from apiswitch.db.models import ApiToken, ApiTokenUnifiedModel, AuxiliarySettings, SchemaMetadata, SystemSetting, UnifiedModel
from apiswitch.db.session import SessionLocal, engine

SCHEMA_GENERATION = 2
_NEW_TABLES = {"schema_metadata", "provider_instances", "upstream_models", "auxiliary_settings"}


def _sqlite_path() -> Path | None:
    if not settings.database_url.startswith("sqlite:///") or settings.database_url == "sqlite:///:memory:":
        return None
    return Path(settings.database_url.removeprefix("sqlite:///"))


def _backup_sqlite(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # sqlite3.Connection.__exit__ commits or rolls back but does not close the
    # connection.  Explicit closing is required before a Windows rename.
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def _inspect_sqlite(path: Path) -> tuple[set[str], int | None]:
    with closing(sqlite3.connect(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        generation = None
        if "schema_metadata" in tables:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(schema_metadata)")}
            if "generation" in columns:
                row = connection.execute("SELECT generation FROM schema_metadata ORDER BY generation DESC LIMIT 1").fetchone()
                generation = row[0] if row else None
        return tables, generation


def _reset_legacy_database(path: Path) -> tuple[str, Path]:
    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup = path.parent / "backups" / f"apiswitch-legacy-{timestamp}.db"
    legacy = path.with_suffix(f".legacy-{timestamp}.db")
    sequence = 1
    while backup.exists() or legacy.exists():
        backup = path.parent / "backups" / f"apiswitch-legacy-{timestamp}-{sequence}.db"
        legacy = path.with_suffix(f".legacy-{timestamp}-{sequence}.db")
        sequence += 1
    _backup_sqlite(path, backup)
    try:
        path.replace(legacy)
        return str(backup), legacy
    except Exception:
        # A successful backup is not enough: the original remains authoritative
        # until the fresh database is fully initialized.
        raise


def _remove_sqlite_files(path: Path) -> None:
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if candidate.exists():
            candidate.unlink()


def _ensure_generation_two_columns(path: Path | None) -> None:
    """Apply safe additive fixes within generation 2 without importing old data."""
    if path is None or not path.exists():
        return
    with closing(sqlite3.connect(path)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(request_logs)")}
        if columns and "first_token_latency_ms" not in columns:
            connection.execute("ALTER TABLE request_logs ADD COLUMN first_token_latency_ms FLOAT")
        if columns and "api_token_prefix_snapshot" not in columns:
            connection.execute("ALTER TABLE request_logs ADD COLUMN api_token_prefix_snapshot VARCHAR(32)")
        breaker_columns = {row[1] for row in connection.execute("PRAGMA table_info(circuit_breakers)")}
        additions = {
            "half_open_at": "DATETIME",
            "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
            "failure_threshold": "INTEGER NOT NULL DEFAULT 3",
        }
        for name, definition in additions.items():
            if breaker_columns and name not in breaker_columns:
                connection.execute(f"ALTER TABLE circuit_breakers ADD COLUMN {name} {definition}")
        batch_columns={row[1] for row in connection.execute("PRAGMA table_info(batch_jobs)")}
        for name in ("output_file_id","error_file_id"):
            if batch_columns and name not in batch_columns:connection.execute(f"ALTER TABLE batch_jobs ADD COLUMN {name} VARCHAR(64)")
        workflow_columns={row[1] for row in connection.execute("PRAGMA table_info(auxiliary_workflows)")}
        if workflow_columns and "priority" not in workflow_columns:connection.execute("ALTER TABLE auxiliary_workflows ADD COLUMN priority INTEGER NOT NULL DEFAULT 100")
        budget_columns={row[1] for row in connection.execute("PRAGMA table_info(budgets)")}
        budget_additions={
            "billing_mode":"VARCHAR(32) NOT NULL DEFAULT 'token_cost'",
            "period_type":"VARCHAR(32) NOT NULL DEFAULT 'calendar_month'",
            "request_limit":"INTEGER",
            "request_count":"INTEGER NOT NULL DEFAULT 0",
            "period_started_at":"DATETIME",
        }
        for name,definition in budget_additions.items():
            if budget_columns and name not in budget_columns:connection.execute(f"ALTER TABLE budgets ADD COLUMN {name} {definition}")
        connection.commit()


def init_database() -> None:
    """Create generation 2, or atomically preserve and replace a legacy SQLite DB."""
    db_path = _sqlite_path()
    reset_from_backup: str | None = None
    legacy_path: Path | None = None
    if db_path and db_path.exists():
        tables, generation = _inspect_sqlite(db_path)
        if tables and (generation != SCHEMA_GENERATION or not _NEW_TABLES.issubset(tables)):
            engine.dispose()
            reset_from_backup, legacy_path = _reset_legacy_database(db_path)
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_generation_two_columns(db_path)
        with SessionLocal() as db:
            metadata = db.scalar(select(SchemaMetadata).where(SchemaMetadata.generation == SCHEMA_GENERATION))
            if metadata is None:
                db.add(SchemaMetadata(generation=SCHEMA_GENERATION, app_version=__version__, reset_from_backup=reset_from_backup))
            if db.get(AuxiliarySettings, 1) is None:
                db.add(AuxiliarySettings(id=1, mode="global_pool"))
            defaults = {"preferred_port": 8080, "upload_limit_bytes": 20 * 1024 * 1024, "template_catalog_version": "2026.07"}
            for key, value in defaults.items():
                if db.get(SystemSetting, key) is None:
                    db.add(SystemSetting(key=key, value_json=value))
            # Generation-two builds initially allowed every token to call every
            # unified model. Preserve that access exactly once during upgrade;
            # fresh and subsequently created tokens use an explicit empty-by-
            # default allow list.
            scope_marker = db.get(SystemSetting, "token_model_scope_initialized")
            if scope_marker is None:
                token_ids = list(db.scalars(select(ApiToken.id)).all())
                model_ids = list(db.scalars(select(UnifiedModel.id)).all())
                for token_id in token_ids:
                    for model_id in model_ids:
                        db.add(ApiTokenUnifiedModel(api_token_id=token_id, unified_model_id=model_id))
                db.add(SystemSetting(key="token_model_scope_initialized", value_json=True))
            db.commit()
    except Exception:
        if db_path and legacy_path:
            engine.dispose()
            _remove_sqlite_files(db_path)
            legacy_path.replace(db_path)
        raise
