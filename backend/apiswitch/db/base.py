from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    """Return naive UTC for SQLite DateTime columns without deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass
