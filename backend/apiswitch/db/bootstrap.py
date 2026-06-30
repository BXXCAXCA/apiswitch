from apiswitch.db.base import Base
from apiswitch.db.seed import seed_default_data
from apiswitch.db.session import SessionLocal, engine


def init_database() -> None:
    """Create stage-2 development tables and seed defaults.

    Alembic remains the canonical migration path. This bootstrap keeps local
    development and tests runnable even before a user has executed migrations.
    """
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_data(db)
