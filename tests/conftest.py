# AI Sharc — pytest fixtures and helpers. No real external calls in any test:
# the scanner is monkeypatched, the mailer is the console backend.
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/root/projects/AI-Sharc")

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

from app import config  # noqa: E402
config.settings.secret_key = "test-secret-key-not-for-production"

from app.db import Base, get_db  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    import tests.helpers as helpers
    helpers.set_session_factory(TestingSession)
    # No real HTTP in tests: stub the scanner.
    import app.scanner as scanner
    monkeypatch.setattr(scanner, "scan_site", lambda url: (
        "C", "The basics are there, but agents can't fully read or trust the site.",
        [{"title": "Services described in text",
          "detail": "Your pages name what you sell in text.",
          "source": f"Source: {url.rstrip('/')} · checked 2026-11-11", "ok": True},
         {"title": "Service area not stated in text",
          "detail": "We couldn't find the towns you serve written as text.",
          "source": f"Source: {url.rstrip('/')} · checked 2026-11-11", "ok": False},
         {"title": "Phone number isn't tappable",
          "detail": "We couldn't find your phone number as a tap-to-call link.",
          "source": f"Source: {url.rstrip('/')} · checked 2026-11-11", "ok": False},
         {"title": "Contact info easy to find",
          "detail": "A contact page exists with a phone number.",
          "source": f"Source: {url.rstrip('/')}/contact · checked 2026-11-11", "ok": True},
         {"title": "Contact details consistent",
          "detail": "The same phone number appears on both pages.",
          "source": f"Source: {url.rstrip('/')} · checked 2026-11-11", "ok": True}]))

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    helpers.set_session_factory(None)
