from sqlalchemy import select

from app.models.book import Book, BookVisibility
from app.models.user import User


def test_private_shared_access_control(client):
    c, Session = client

    with Session() as db:
        owner = db.scalar(select(User))
        other = User(email="other@example.com")
        db.add(other)
        db.flush()
        db.add(Book(title="Priv", author="A", file_type="fb2", visibility=BookVisibility.private, owner_id=other.id))
        db.add(Book(title="Shared", author="A", file_type="fb2", visibility=BookVisibility.shared, owner_id=other.id))
        db.commit()

    resp = c.get("/api/v1/library")
    assert resp.status_code == 200
    titles = [x["title"] for x in resp.json()["items"]]
    assert "Shared" in titles
    assert "Priv" not in titles
