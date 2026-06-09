"""Tests for src.core.ssrf.safe_get -- SSRF-safe fetch with redirect re-validation
and a response-size cap."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from src.core.ssrf import MAX_FETCH_BYTES, safe_get


async def _noop(_url: str) -> None:
    return None


@respx.mock
async def test_returns_content_on_200():
    respx.get("https://example.com/feed").mock(
        return_value=httpx.Response(200, text="hello world")
    )
    with patch("src.core.ssrf.assert_safe_url", _noop):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(client, "https://example.com/feed")
    assert resp.status_code == 200
    assert resp.text == "hello world"


@respx.mock
async def test_follows_safe_redirect():
    respx.get("https://example.com/a").mock(
        return_value=httpx.Response(302, headers={"location": "https://example.com/b"})
    )
    respx.get("https://example.com/b").mock(return_value=httpx.Response(200, text="final"))
    with patch("src.core.ssrf.assert_safe_url", _noop):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(client, "https://example.com/a")
    assert resp.status_code == 200
    assert resp.text == "final"


@respx.mock
async def test_redirect_to_unsafe_host_is_blocked():
    """A redirect Location pointing at a private IP must be re-validated and rejected."""
    respx.get("https://example.com/a").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
    )

    async def _block_metadata(url: str) -> None:
        if "169.254.169.254" in url:
            raise ValueError("blocked private/reserved IP")

    with patch("src.core.ssrf.assert_safe_url", _block_metadata):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            with pytest.raises(ValueError, match="blocked"):
                await safe_get(client, "https://example.com/a")


@respx.mock
async def test_oversized_response_is_rejected():
    big = "x" * (MAX_FETCH_BYTES + 1)
    respx.get("https://example.com/big").mock(return_value=httpx.Response(200, text=big))
    with patch("src.core.ssrf.assert_safe_url", _noop):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            with pytest.raises(ValueError, match="exceeded"):
                await safe_get(client, "https://example.com/big")


@respx.mock
async def test_too_many_redirects_is_rejected():
    # Each hop redirects to the next; exceed the cap.
    for i in range(10):
        respx.get(f"https://example.com/{i}").mock(
            return_value=httpx.Response(302, headers={"location": f"https://example.com/{i + 1}"})
        )
    with patch("src.core.ssrf.assert_safe_url", _noop):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            with pytest.raises(ValueError, match="[Tt]oo many redirects"):
                await safe_get(client, "https://example.com/0")


@respx.mock
async def test_custom_headers_are_sent():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["if-none-match"] = request.headers.get("if-none-match", "")
        return httpx.Response(304)

    respx.get("https://example.com/feed").mock(side_effect=handler)
    with patch("src.core.ssrf.assert_safe_url", _noop):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(
                client, "https://example.com/feed", headers={"If-None-Match": "abc"}
            )
    assert resp.status_code == 304
    assert captured["if-none-match"] == "abc"
