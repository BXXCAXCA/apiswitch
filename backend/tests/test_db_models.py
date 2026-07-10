from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from apiswitch.db.base import Base
from apiswitch.db.models import Provider, ProviderConnection, ProviderNode


def test_db_models_create_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = inspect(engine).get_table_names()
    assert "providers" in tables
    assert "provider_connections" in tables
    assert "provider_nodes" in tables
    assert "model_pricing" in tables
    assert "quota_snapshots" in tables
    assert "usage_history" in tables
    assert "session_affinity" in tables
    assert "unified_models" in tables
    assert "request_logs" in tables

    with Session(engine) as session:
        provider = Provider(name="mock-main", type="mock", base_url="mock://local")
        session.add(provider)
        session.flush()

        connection = ProviderConnection(
            provider_id=provider.id,
            name="default-account",
            auth_type="api_key",
            account_label="local",
        )
        session.add(connection)
        session.flush()

        session.add(
            ProviderNode(
                provider_id=provider.id,
                connection_id=connection.id,
                name="local-node",
                base_url="mock://local",
            )
        )
        session.commit()

        assert session.query(Provider).count() == 1
        assert session.query(ProviderConnection).count() == 1
        assert session.query(ProviderNode).count() == 1
