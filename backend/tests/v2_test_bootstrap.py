from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from apiswitch.db import bootstrap
from apiswitch.db.models import ApiToken, ApiTokenUnifiedModel, SchemaMetadata, UnifiedModel


def _configure_isolated_database(monkeypatch, path: Path):
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(bootstrap.settings, "database_url", f"sqlite:///{path.as_posix()}")
    monkeypatch.setattr(bootstrap, "engine", engine)
    monkeypatch.setattr(bootstrap, "SessionLocal", sessionmaker(bind=engine, future=True))
    return engine


def test_legacy_database_is_closed_backed_up_and_replaced(monkeypatch, tmp_path: Path):
    database = tmp_path / "apiswitch.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE provider_connections (id INTEGER PRIMARY KEY)")
    engine = _configure_isolated_database(monkeypatch, database)

    bootstrap.init_database()

    tables = set(inspect(engine).get_table_names())
    assert {"schema_metadata", "provider_instances", "upstream_models"}.issubset(tables)
    assert list((tmp_path / "backups").glob("apiswitch-legacy-*.db"))
    assert list(tmp_path.glob("apiswitch.legacy-*.db"))


def test_failed_fresh_initialization_restores_legacy_database(monkeypatch, tmp_path: Path):
    database = tmp_path / "apiswitch.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE provider_connections (id INTEGER PRIMARY KEY)")
    _configure_isolated_database(monkeypatch, database)
    monkeypatch.setattr(bootstrap.Base.metadata, "create_all", lambda **_: (_ for _ in ()).throw(RuntimeError("simulated initialization failure")))

    with pytest.raises(RuntimeError, match="simulated initialization failure"):
        bootstrap.init_database()

    with closing(sqlite3.connect(database)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "provider_connections" in tables
    assert "provider_instances" not in tables


def test_generation_two_database_gets_safe_additive_log_column(monkeypatch, tmp_path: Path):
    database = tmp_path / "apiswitch.db"
    engine = _configure_isolated_database(monkeypatch, database)
    bootstrap.Base.metadata.create_all(bind=engine)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("INSERT INTO schema_metadata (generation, app_version, created_at) VALUES (2, 'test', CURRENT_TIMESTAMP)")
        connection.execute("ALTER TABLE request_logs RENAME TO request_logs_new")
        columns = connection.execute("PRAGMA table_info(request_logs_new)").fetchall()
        kept = [row for row in columns if row[1] != "first_token_latency_ms"]
        definitions = ", ".join(f'"{row[1]}" {row[2]}' for row in kept)
        connection.execute(f"CREATE TABLE request_logs ({definitions})")
        connection.execute("DROP TABLE request_logs_new")
        connection.commit()

    bootstrap.init_database()

    with closing(sqlite3.connect(database)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(request_logs)")}
    assert "first_token_latency_ms" in columns


def test_generation_two_budget_rows_gain_period_and_request_count_columns(monkeypatch, tmp_path: Path):
    database = tmp_path / "apiswitch.db"
    engine = _configure_isolated_database(monkeypatch, database)
    bootstrap.Base.metadata.create_all(bind=engine)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("INSERT INTO schema_metadata (generation, app_version, created_at) VALUES (2, 'test', CURRENT_TIMESTAMP)")
        connection.execute("ALTER TABLE budgets RENAME TO budgets_new")
        connection.execute("""CREATE TABLE budgets (
            id INTEGER PRIMARY KEY,
            name VARCHAR(128) NOT NULL,
            scope VARCHAR(32) NOT NULL,
            scope_id VARCHAR(128),
            monthly_limit FLOAT,
            currency VARCHAR(16) NOT NULL,
            enabled BOOLEAN NOT NULL,
            spent_amount FLOAT NOT NULL,
            alert_threshold_percent INTEGER NOT NULL,
            enforcement_action VARCHAR(32) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )""")
        connection.execute("INSERT INTO budgets VALUES (1,'old monthly','global',NULL,25,'USD',1,3,80,'reject',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
        connection.execute("DROP TABLE budgets_new")
        connection.commit()

    bootstrap.init_database()

    with closing(sqlite3.connect(database)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(budgets)")}
        row = connection.execute("SELECT monthly_limit, spent_amount, billing_mode, period_type, request_count FROM budgets WHERE id=1").fetchone()
    assert {"billing_mode", "period_type", "request_limit", "request_count", "period_started_at"}.issubset(columns)
    assert row == (25.0, 3.0, "token_cost", "calendar_month", 0)


def test_existing_generation_two_tokens_keep_model_access_once(monkeypatch, tmp_path: Path):
    database = tmp_path / "apiswitch.db"
    engine = _configure_isolated_database(monkeypatch, database)
    bootstrap.Base.metadata.create_all(bind=engine)
    session_factory=sessionmaker(bind=engine,future=True)
    with session_factory() as db:
        db.add(SchemaMetadata(generation=2,app_version="test"))
        model=UnifiedModel(name="existing-model",enabled_protocols_json=["openai_chat"])
        token=ApiToken(name="existing-token",token_prefix="ask_existing",token_hash="test-hash",scopes_json=["gateway:invoke"])
        db.add_all([model,token]);db.commit();model_id=model.id;token_id=token.id

    bootstrap.init_database()

    with session_factory() as db:
        bindings=list(db.scalars(select(ApiTokenUnifiedModel).where(ApiTokenUnifiedModel.api_token_id==token_id)).all())
        assert [row.unified_model_id for row in bindings]==[model_id]
    bootstrap.init_database()
    with session_factory() as db:
        assert len(list(db.scalars(select(ApiTokenUnifiedModel).where(ApiTokenUnifiedModel.api_token_id==token_id)).all()))==1
