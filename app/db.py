# AI Sharc — SQLAlchemy setup. Postgres in production, SQLite for dev/tests.
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def make_engine(url=None):
    url = url or settings.database_url
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)


def init_db_with_engine(eng):
    """Test helper: create tables on an explicit engine."""
    from app import models  # noqa: F401
    Base.metadata.create_all(eng)


os.environ.setdefault("SQLALCHEMY_SILENCE_UBER_WARNING", "1")
