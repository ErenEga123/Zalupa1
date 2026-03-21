from datetime import datetime, timedelta, timezone


def test_progress_antiregression(client):
    c, _ = client
    now = datetime.now(timezone.utc)

    first = c.post(
        "/api/v1/progress",
        json={"book_id": "book-1", "chapter_id": 1, "position": 12, "updated_at": now.isoformat()},
    )
    assert first.status_code == 200
    assert first.json()["accepted"] is True

    stale = c.post(
        "/api/v1/progress",
        json={"book_id": "book-1", "chapter_id": 1, "position": 5, "updated_at": (now - timedelta(seconds=30)).isoformat()},
    )
    assert stale.status_code == 200
    assert stale.json()["accepted"] is False
    assert stale.json()["server_progress"]["position"] == 12


def test_concurrent_progress_ordering(client):
    c, _ = client
    now = datetime.now(timezone.utc)

    newer = c.post(
        "/api/v1/progress",
        json={"book_id": "book-2", "chapter_id": 2, "position": 88, "updated_at": (now + timedelta(seconds=4)).isoformat()},
    )
    older = c.post(
        "/api/v1/progress",
        json={"book_id": "book-2", "chapter_id": 1, "position": 15, "updated_at": now.isoformat()},
    )

    assert newer.json()["accepted"] is True
    assert older.json()["accepted"] is False
    assert older.json()["server_progress"]["chapter_id"] == 2
