from io import BytesIO


def test_upload_size_limit(client, monkeypatch):
    c, _ = client
    from app.api.v1 import books as books_module

    old_limit = books_module.settings.max_book_size_mb
    books_module.settings.max_book_size_mb = 0
    try:
        data = {
            "title": "X",
            "author": "Y",
            "visibility": "private",
        }
        files = {"file": ("x.fb2", BytesIO(b"<fb2></fb2>"), "application/octet-stream")}

        resp = c.post("/api/v1/books/upload", data=data, files=files)
        assert resp.status_code == 413
    finally:
        books_module.settings.max_book_size_mb = old_limit


def test_upload_file_only_mode(client):
    c, _ = client
    payload = b"<?xml version='1.0'?><FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'><body><section><p>a</p></section></body></FictionBook>"
    resp = c.post(
        "/api/v1/books/upload",
        files={"file": ("simple_book.fb2", payload, "application/octet-stream")},
    )
    assert resp.status_code == 200


def test_duplicate_detection_by_sha256(client, tmp_path):
    c, _ = client
    payload = b"<?xml version='1.0'?><FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'><body><section><p>a</p></section></body></FictionBook>"

    data = {"title": "D1", "author": "A", "visibility": "private"}
    files = {"file": ("d.fb2", payload, "application/octet-stream")}
    first = c.post("/api/v1/books/upload", data=data, files=files)
    assert first.status_code == 200

    second = c.post("/api/v1/books/upload", data=data, files=files)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


def test_duplicate_safe_import_naming(client):
    c, _ = client
    body = b"<?xml version='1.0'?><FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'><body><section><p>a</p></section></body></FictionBook>"

    first = c.post(
        "/api/v1/books/upload",
        data={"title": "Same", "author": "A", "visibility": "private"},
        files={"file": ("one.fb2", body, "application/octet-stream")},
    )
    second = c.post(
        "/api/v1/books/upload",
        data={"title": "Same", "author": "A", "visibility": "private"},
        files={"file": ("two.fb2", body + b"x", "application/octet-stream")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["book_id"] != second.json()["book_id"]
