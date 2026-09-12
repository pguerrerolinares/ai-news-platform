"""Tests for src.core.ssrf.safe_get -- SSRF-safe fetch with redirect re-validation,
IP pinning, and a response-size cap."""

from __future__ import annotations

import gzip
from unittest.mock import patch

import httpx
import pytest
import respx

from src.core.ssrf import MAX_FETCH_BYTES, safe_get

# assert_safe_url is patched to return this fixed, public (TEST-NET-3, RFC 5737)
# IP for every hostname in these tests -- safe_get must connect to exactly this
# literal, never to the original hostname (see test_host_and_sni_are_pinned).
_PINNED_IP = "203.0.113.5"


async def _pin(_url: str) -> str:
    return _PINNED_IP


@respx.mock
async def test_returns_content_on_200():
    respx.get(f"https://{_PINNED_IP}/feed").mock(
        return_value=httpx.Response(200, text="hello world")
    )
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(client, "https://example.com/feed")
    assert resp.status_code == 200
    assert resp.text == "hello world"


@respx.mock
async def test_host_and_sni_are_pinned_to_original_hostname():
    """The wire request must target the validated IP while Host/SNI stay the
    original hostname -- otherwise the server can't route to the right vhost."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url_host"] = request.url.host
        captured["host_header"] = request.headers.get("host")
        captured["sni_hostname"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, text="ok")

    respx.get(f"https://{_PINNED_IP}/feed").mock(side_effect=handler)
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(client, "https://example.com/feed")
    assert resp.status_code == 200
    assert captured["url_host"] == _PINNED_IP
    assert captured["host_header"] == "example.com"
    assert captured["sni_hostname"] == "example.com"


@respx.mock
async def test_follows_safe_redirect():
    respx.get(f"https://{_PINNED_IP}/a").mock(
        return_value=httpx.Response(302, headers={"location": "https://example.com/b"})
    )
    respx.get(f"https://{_PINNED_IP}/b").mock(return_value=httpx.Response(200, text="final"))
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(client, "https://example.com/a")
    assert resp.status_code == 200
    assert resp.text == "final"


@respx.mock
async def test_redirect_to_unsafe_host_is_blocked():
    """A redirect Location pointing at a private IP must be re-validated and rejected."""
    respx.get(f"https://{_PINNED_IP}/a").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
    )

    async def _block_metadata(url: str) -> str:
        if "169.254.169.254" in url:
            raise ValueError("blocked private/reserved IP")
        return _PINNED_IP

    with patch("src.core.ssrf.assert_safe_url", _block_metadata):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            with pytest.raises(ValueError, match="blocked"):
                await safe_get(client, "https://example.com/a")


@respx.mock
async def test_oversized_response_is_rejected():
    big = "x" * (MAX_FETCH_BYTES + 1)
    respx.get(f"https://{_PINNED_IP}/big").mock(return_value=httpx.Response(200, text=big))
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            with pytest.raises(ValueError, match="exceeded"):
                await safe_get(client, "https://example.com/big")


@respx.mock
async def test_too_many_redirects_is_rejected():
    # Each hop redirects to the next; exceed the cap.
    for i in range(10):
        respx.get(f"https://{_PINNED_IP}/{i}").mock(
            return_value=httpx.Response(302, headers={"location": f"https://example.com/{i + 1}"})
        )
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            with pytest.raises(ValueError, match="[Tt]oo many redirects"):
                await safe_get(client, "https://example.com/0")


@respx.mock
async def test_compressed_body_is_decoded_once():
    """A gzip/brotli response must be decoded exactly once.

    ``aiter_bytes`` already decompresses the stream, so the reconstructed
    Response must drop the ``Content-Encoding`` header — otherwise httpx
    tries to decompress the already-plain body again and raises DecodingError.
    """
    payload = b"<rss><item>hello</item></rss>"
    respx.get(f"https://{_PINNED_IP}/gz").mock(
        return_value=httpx.Response(
            200, headers={"Content-Encoding": "gzip"}, content=gzip.compress(payload)
        )
    )
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(client, "https://example.com/gz")
    assert resp.text == payload.decode()


@respx.mock
async def test_custom_headers_are_sent():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["if-none-match"] = request.headers.get("if-none-match", "")
        return httpx.Response(304)

    respx.get(f"https://{_PINNED_IP}/feed").mock(side_effect=handler)
    with patch("src.core.ssrf.assert_safe_url", _pin):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await safe_get(
                client, "https://example.com/feed", headers={"If-None-Match": "abc"}
            )
    assert resp.status_code == 304
    assert captured["if-none-match"] == "abc"
