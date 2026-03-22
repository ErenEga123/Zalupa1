def test_upload_uses_embedded_fb2_metadata(client):
    c, _ = client

    fb2 = b"""<?xml version='1.0' encoding='utf-8'?>
<FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'>
  <description>
    <title-info>
      <book-title>War and Peace</book-title>
      <author>
        <first-name>Leo</first-name>
        <last-name>Tolstoy</last-name>
      </author>
      <sequence name='Great Novels' number='1'/>
    </title-info>
  </description>
  <body><section><title><p>One</p></title><p>Hello</p></section></body>
</FictionBook>"""

    upload = c.post(
        '/api/v1/books/upload',
        data={'title': 'Manual Title', 'author': 'Unknown', 'visibility': 'private'},
        files={'file': ('book.fb2', fb2, 'application/octet-stream')},
    )
    assert upload.status_code == 200
    book_id = upload.json()['book_id']

    lib = c.get('/api/v1/library?page=1&page_size=20')
    assert lib.status_code == 200
    row = next(x for x in lib.json()['items'] if x['id'] == book_id)

    assert row['title'] == 'War and Peace'
    assert row['author'] == 'Leo Tolstoy'
    assert row['series'] == 'Great Novels'
