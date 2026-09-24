"""SQLAlchemy engine/session setup. Synchronous on purpose — every route in
this app is either already sync or does a small amount of I/O per request,
so a sync engine (run in FastAPI's threadpool for async routes) is simpler
than wiring up async SQLAlchemy for no real benefit at this scale.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope() -> Iterator[Session]:
    """Use as `with session_scope() as db:` in plain functions (the data
    layer, seed scripts) — commits on success, rolls back on exception."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Creates all tables if they don't exist yet. No migration framework
    (Alembic) for this project's scope — schema changes during development
    are handled by editing the models and recreating the dev database."""
    import app.db_models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)

    # create_all() never alters a table that already exists, and there's no
    # migration framework — so columns added later are patched in here, once
    # and idempotently, instead of forcing a dev database reset.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS deleted_at VARCHAR"))
        conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS deleted_by VARCHAR"))
