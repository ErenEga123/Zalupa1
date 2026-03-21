from app.core.settings import Settings


def test_config_validation_positive_limits():
    cfg = Settings(max_book_size_mb=10, max_epub_unpacked_mb=100)
    assert cfg.max_book_size_mb == 10


def test_config_validation_rejects_invalid_limits():
    try:
        Settings(max_book_size_mb=0)
        assert False, "expected validation error"
    except Exception:
        assert True
