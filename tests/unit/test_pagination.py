"""Unit tests for pagination utilities."""

from __future__ import annotations

from starlette.responses import Response

from src.api.pagination import set_total_count_header


class TestSetTotalCountHeader:
    def test_sets_header(self) -> None:
        response = Response()
        set_total_count_header(response, 42)
        assert response.headers["X-Total-Count"] == "42"

    def test_sets_zero(self) -> None:
        response = Response()
        set_total_count_header(response, 0)
        assert response.headers["X-Total-Count"] == "0"
