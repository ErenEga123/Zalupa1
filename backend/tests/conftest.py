import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_reader.db")
os.environ.setdefault("JWT_SECRET", "test-secret-123456")
os.environ.setdefault("MAX_BOOK_SIZE_MB", "2")
os.environ.setdefault("MAX_EPUB_UNPACKED_MB", "10")
os.environ.setdefault("BOT_TOKEN", "123456:TEST")

from app.db.session import Base
from app.main import app
from app.models.user import User
from app.services.jwt_service import create_access_token


@pytest.fixture(scope="session", autouse=True)
def setup_env():
    Path("/data/library/books").mkdir(parents=True, exist_ok=True)
    Path("/data/temp").mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    from app.db import session as session_mod

    session_mod.engine = engine
    session_mod.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        user = User(email="reader@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user)

    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        c.test_user_id = user.id
        yield c, TestingSessionLocal


def make_fb2(path: Path):
    path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'>
  <description><title-info><book-title>FB2 Sample</book-title></title-info></description>
  <body>
    <section><title><p>Chapter A</p></title><p>Hello world</p></section>
    <section><title><p>Chapter B</p></title><p>Next section</p></section>
  </body>
</FictionBook>""",
        encoding="utf-8",
    )
