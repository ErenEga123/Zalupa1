from pathlib import Path

from app.services.storage_service import ensure_directories


def test_startup_directory_initialization(tmp_path, monkeypatch):
    from app.services import storage_service

    storage_service.settings.library_root = tmp_path / "lib/books"
    storage_service.settings.temp_root = tmp_path / "temp"
    ensure_directories()

    assert (tmp_path / "lib/books").exists()
    assert (tmp_path / "temp").exists()
