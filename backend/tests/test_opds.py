def test_opds_feed_is_valid_and_paginated(client):
    c, _ = client
    root = c.get('/opds?page=1&page_size=1')
    assert root.status_code == 200
    assert '<feed' in root.text
    books = c.get('/opds/books?page=1&page_size=1')
    assert books.status_code == 200
    assert '<feed' in books.text
