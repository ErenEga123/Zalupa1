import hashlib
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, is_admin_user
from app.core.settings import get_settings
from app.db.session import get_db
from app.models.book import Book, BookFile, BookFileType, BookVisibility, Chapter, ProcessingStatus, ProcessingTask
from app.models.user import User
from app.schemas.books import BookCreateResult, BookVisibilityIn, ChapterContentOut, ChapterOut
from app.services.metadata_service import extract_metadata
from app.services.storage_service import get_book_paths


router = APIRouter()
settings = get_settings()


def _can_access(book: Book, user: User) -> bool:
    return book.owner_id == user.id or book.visibility == BookVisibility.shared or is_admin_user(user)


@router.post("/upload", response_model=BookCreateResult)
async def upload_book(
    title: str | None = Form(None),
    author: str | None = Form(None),
    series: str | None = Form(None),
    visibility: str = Form("private"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BookCreateResult:
    suffix = (Path(file.filename or "").suffix or "").lower().lstrip(".")
    if suffix not in {"epub", "fb2", "pdf"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    max_size = settings.max_book_size_mb * 1024 * 1024
    upload_tmp_id = __import__("uuid").uuid4().hex
    tmp = settings.temp_root / f"upload_{upload_tmp_id}.{suffix}"
    hasher = hashlib.sha256()
    total_size = 0

    with tmp.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_size:
                tmp.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large")
            hasher.update(chunk)
            out.write(chunk)

    parsed = extract_metadata(tmp, suffix)
    fallback_title = Path(file.filename or "").stem or "Untitled"
    resolved_title = (parsed.title or title or fallback_title).strip()
    resolved_author = (parsed.author or author or "Unknown").strip()
    resolved_series = (parsed.series or series or "").strip() or None

    sha256 = hasher.hexdigest()
    existing = db.scalar(select(BookFile).where(BookFile.sha256 == sha256))
    if existing:
        existing_book = db.get(Book, existing.book_id)
        if existing_book and (existing_book.owner_id == user.id or existing_book.visibility == BookVisibility.shared or is_admin_user(user)):
            tmp.unlink(missing_ok=True)
            return BookCreateResult(book_id=existing_book.id, duplicate=True, message="Duplicate file detected; using existing import")

    book_uuid = str(__import__("uuid").uuid4())
    file_type = BookFileType[suffix]
    book = Book(
        id=book_uuid,
        title=resolved_title,
        author=resolved_author,
        series=resolved_series,
        file_type=file_type,
        visibility=BookVisibility(visibility if visibility in {"private", "shared"} else "private"),
        owner_id=user.id,
    )
    db.add(book)
    db.flush()

    original_path, processed_root, _ = get_book_paths(book_uuid, suffix)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), str(original_path))

    db.add(
        BookFile(
            book_id=book_uuid,
            original_path=str(original_path),
            processed_path=str(processed_root),
            file_size=total_size,
            sha256=sha256,
        )
    )
    db.add(ProcessingTask(book_id=book_uuid, status=ProcessingStatus.pending, attempt_count=0))
    db.commit()

    return BookCreateResult(book_id=book_uuid, duplicate=False, message="Uploaded and queued for processing")


@router.get("/{book_id}/chapters", response_model=list[ChapterOut])
def list_chapters(book_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ChapterOut]:
    book = db.get(Book, book_id)
    if not book or not _can_access(book, user):
        raise HTTPException(status_code=404, detail="Book not found")

    chapters = db.scalars(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order_index.asc())).all()
    return [
        ChapterOut(
            id=c.id,
            title=c.title,
            order_index=c.order_index,
            chapter_type=c.chapter_type.value,
        )
        for c in chapters
    ]


@router.get("/{book_id}/chapter/{chapter_id}", response_model=ChapterContentOut)
def get_chapter(book_id: str, chapter_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ChapterContentOut:
    book = db.get(Book, book_id)
    if not book or not _can_access(book, user):
        raise HTTPException(status_code=404, detail="Book not found")

    chapter = db.scalar(select(Chapter).where(Chapter.id == chapter_id, Chapter.book_id == book_id))
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    prev_id = db.scalar(
        select(Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.order_index < chapter.order_index)
        .order_by(Chapter.order_index.desc())
        .limit(1)
    )
    next_id = db.scalar(
        select(Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.order_index > chapter.order_index)
        .order_by(Chapter.order_index.asc())
        .limit(1)
    )

    content = Path(chapter.content_path).read_text(encoding="utf-8", errors="ignore")
    return ChapterContentOut(
        id=chapter.id,
        title=chapter.title,
        order_index=chapter.order_index,
        chapter_type=chapter.chapter_type.value,
        content=content,
        prev_chapter_id=prev_id,
        next_chapter_id=next_id,
    )


@router.get("/{book_id}/download")
def download_original(book_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    book = db.get(Book, book_id)
    if not book or not _can_access(book, user):
        raise HTTPException(status_code=404, detail="Book not found")
    book_file = db.scalar(select(BookFile).where(BookFile.book_id == book_id))
    if not book_file:
        raise HTTPException(status_code=404, detail="File missing")
    path = Path(book_file.original_path)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@router.patch("/{book_id}/visibility")
def update_visibility(
    book_id: str,
    payload: BookVisibilityIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.owner_id != user.id and not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Only owner/admin can change visibility")

    book.visibility = BookVisibility(payload.visibility)
    db.commit()
    return {"ok": True, "book_id": book.id, "visibility": book.visibility.value}


@router.get("/{book_id}/cover")
def get_cover(book_id: str, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book or book.visibility != BookVisibility.shared:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.cover_path:
        raise HTTPException(status_code=404, detail="Cover not found")
    path = Path(book.cover_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover file missing")
    return FileResponse(path, media_type="image/jpeg", filename=f"{book_id}.jpg")
