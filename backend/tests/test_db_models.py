from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from apiswitch.db.base import Base
from apiswitch.db.models import Provider


def test_db_models_create_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = inspect(engine).get_table_names()
    assert "providers" in tables
    assert "unified_models" in tables
    assert "request_logs" in tables

    with Session(engine) as session:
        session.add(Provider(name="mock-main", type="mock", base_url="mock://local"))
        session.commit()
        assert session.query(Provider).count() == 1
