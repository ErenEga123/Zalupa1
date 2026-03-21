from pathlib import Path

from app.core.settings import get_settings


settings = get_settings()


def ensure_directories() -> None:
    settings.library_root.mkdir(parents=True, exist_ok=True)
    settings.temp_root.mkdir(parents=True, exist_ok=True)


def get_book_paths(book_id: str, ext: str) -> tuple[Path, Path, Path]:
    base = settings.library_root / book_id
    original = base / f"original.{ext}"
    processed = base / "processed"
    cover = base / "cover.jpg"
    processed.mkdir(parents=True, exist_ok=True)
    return original, processed, cover
