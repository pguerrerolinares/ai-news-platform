"""Unit tests for pipeline pre-storage validation."""
from __future__ import annotations

from src.pipeline.validation import validate_extracted_item


class TestPreStorageValidation:
    def test_valid_item_passes(self) -> None:
        item = {"title": "Test Title", "url": "https://example.com", "source": "hackernews"}
        errors = validate_extracted_item(item)
        assert errors == []

    def test_empty_title_rejected(self) -> None:
        item = {"title": "", "url": "https://example.com", "source": "hackernews"}
        errors = validate_extracted_item(item)
        assert any("title" in e for e in errors)

    def test_missing_title_rejected(self) -> None:
        item = {"url": "https://example.com", "source": "hackernews"}
        errors = validate_extracted_item(item)
        assert any("title" in e for e in errors)

    def test_empty_url_rejected(self) -> None:
        item = {"title": "Test", "url": "", "source": "hackernews"}
        errors = validate_extracted_item(item)
        assert any("url" in e for e in errors)

    def test_none_url_rejected(self) -> None:
        item = {"title": "Test", "url": None, "source": "hackernews"}
        errors = validate_extracted_item(item)
        assert any("url" in e for e in errors)

    def test_valid_item_with_optional_fields(self) -> None:
        item = {
            "title": "Test",
            "url": "https://example.com",
            "source": "github",
            "published_at": "2026-02-21T10:00:00Z",
        }
        errors = validate_extracted_item(item)
        assert errors == []
