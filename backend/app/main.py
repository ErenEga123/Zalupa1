from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.router import router as api_router
from app.api.deps import get_current_user
from app.db.init_db import init_db
from app.db.session import get_db
from app.models.book import Book, BookFile, BookVisibility
from app.models.user import User
from app.services.storage_service import ensure_directories
from app.worker.queue import queue_runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    init_db()
    await queue_runner.start()
    try:
        yield
    finally:
        await queue_runner.stop()


app = FastAPI(title="Reader System", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(select(1))
    return {"status": "ok"}


@app.get("/app", response_class=HTMLResponse)
def web_app() -> str:
    return Path("app/web/index.html").read_text(encoding="utf-8")


@app.get("/sw.js")
def service_worker() -> Response:
    body = Path("app/web/sw.js").read_text(encoding="utf-8")
    return Response(content=body, media_type="application/javascript")


@app.get("/manifest.webmanifest")
def manifest() -> Response:
    body = Path("app/web/manifest.webmanifest").read_text(encoding="utf-8")
    return Response(content=body, media_type="application/manifest+json")


@app.get("/app/{asset_path:path}")
def app_assets(asset_path: str):
    path = Path("app/web") / asset_path
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)


@app.get("/opds", response_class=Response)
def opds_root(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(select(Book).where(Book.visibility == BookVisibility.shared).subquery())) or 0
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>reader-system-opds-root</id>
  <title>Reader System Catalog</title>
  <updated>2026-01-01T00:00:00Z</updated>
  <link rel="self" href="/opds?page={page}&page_size={page_size}" />
  <link rel="start" href="/opds" />
  <link rel="subsection" href="/opds/books?page=1&page_size={page_size}" title="Books" />
  <author><name>Reader System</name></author>
  <entry>
    <id>reader-system-opds-books</id>
    <title>Books</title>
    <link rel="subsection" href="/opds/books?page={page}&page_size={page_size}" />
    <content type="text">Shared books: {total}</content>
  </entry>
</feed>'''
    return Response(content=xml, media_type="application/atom+xml;profile=opds-catalog")


@app.get("/opds/books", response_class=Response)
def opds_books(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    offset = (page - 1) * page_size
    base = select(Book).where(Book.visibility == BookVisibility.shared)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    books = db.scalars(base.order_by(Book.created_at.desc()).offset(offset).limit(page_size)).all()

    next_link = ""
    if offset + page_size < total:
        next_link = f'<link rel="next" href="/opds/books?page={page + 1}&page_size={page_size}" />'
    prev_link = ""
    if page > 1:
        prev_link = f'<link rel="previous" href="/opds/books?page={page - 1}&page_size={page_size}" />'

    entries = []
    for b in books:
        file_row = db.scalar(select(BookFile).where(BookFile.book_id == b.id))
        if not file_row:
            continue
        cover_link = f'<link rel="http://opds-spec.org/image" href="/api/v1/books/{b.id}/cover" type="image/jpeg" />' if b.cover_path else ""
        entries.append(
            f'''<entry>
  <id>{b.id}</id>
  <title>{b.title}</title>
  <author><name>{b.author}</name></author>
  <updated>{b.created_at.isoformat()}</updated>
  <link rel="http://opds-spec.org/acquisition" href="/api/v1/books/{b.id}/download" type="application/octet-stream" />
  {cover_link}
</entry>'''
        )

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>reader-system-opds-books</id>
  <title>Reader System Books</title>
  <updated>2026-01-01T00:00:00Z</updated>
  <link rel="self" href="/opds/books?page={page}&page_size={page_size}" />
  {next_link}
  {prev_link}
  {''.join(entries)}
</feed>'''
    return Response(content=xml, media_type="application/atom+xml;profile=opds-catalog")

