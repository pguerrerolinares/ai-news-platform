"""Async HTTP client for the AI News Platform API, used by the MCP server."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

_TIMEOUT = httpx.Timeout(30.0)

_Params = dict[str, str | int | float]


class APIRequestError(Exception):
    """An API call failed; the message is actionable for the calling agent."""


def _validation_detail(body: object, message: str | None) -> str:
    if message:
        return message
    if isinstance(body, dict) and isinstance(body.get("detail"), list):
        parts = []
        for err in body["detail"]:
            loc = err.get("loc") or ["?"]
            parts.append(f"{loc[-1]}: {err.get('msg', 'invalid')}")
        return "; ".join(parts)
    return "request rejected by the API"


def _raise_for_api_error(resp: httpx.Response) -> None:
    """Translate a non-2xx API response into an actionable APIRequestError."""
    if resp.is_success:
        return
    status = resp.status_code
    try:
        body: object = resp.json()
    except ValueError:
        body = None
    error = body.get("error") if isinstance(body, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    message = error.get("message") if isinstance(error, dict) else None

    if code == "NOT_FOUND":
        raise APIRequestError("item not found")
    if code == "EMBEDDING_NOT_FOUND":
        raise APIRequestError("item exists but has no embedding yet; similar unavailable")
    if code == "EMBEDDING_UNAVAILABLE":
        raise APIRequestError(
            "semantic search unavailable (embedding provider down); try mode=keyword"
        )
    if status == 422:
        raise APIRequestError(f"invalid arguments: {_validation_detail(body, message)}")
    if status == 429:
        raise APIRequestError(f"rate limited, retry in {resp.headers.get('Retry-After', '60')}s")
    if status >= 500:
        raise APIRequestError(f"backend unavailable (HTTP {status})")
    raise APIRequestError(f"unexpected API response (HTTP {status}): {message or resp.text[:200]}")


class APIClient:
    """Async client over the REST API; one instance is shared by all tool calls."""

    def __init__(self, base_url: str = "http://localhost:8000", token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=_TIMEOUT)
        self.token = token
        self._token_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _acquire_guest_token(self) -> str:
        try:
            resp = await self._http.post("/api/auth/guest")
        except httpx.TransportError as exc:
            raise APIRequestError(f"backend unavailable ({type(exc).__name__})") from exc
        if resp.status_code != 200:
            raise APIRequestError(
                f"backend unavailable (guest token acquisition failed: HTTP {resp.status_code})"
            )
        return resp.json()["access_token"]

    async def _ensure_token(self) -> None:
        if self.token:
            return
        async with self._token_lock:
            if not self.token:
                self.token = await self._acquire_guest_token()

    async def _refresh_token(self, stale_token: str) -> None:
        """Refresh the guest token once, even if many callers 401 at the same time.

        Same lock as ``_ensure_token``, with the same double-checked pattern: only the
        first caller to grab the lock whose token still equals the one that got the 401
        performs the POST; by the time the rest of the woken-up callers acquire the
        lock, ``self.token`` has already moved on, so they skip the request and just
        retry with the fresh one. N coroutines racing on the same expired token make
        exactly one ``POST /api/auth/guest`` (decision: Paul).
        """
        async with self._token_lock:
            if self.token == stale_token:
                self.token = await self._acquire_guest_token()

    async def _send(
        self, path: str, params: _Params | None, forwarded_for: str | None
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}"}
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        try:
            return await self._http.get(path, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise APIRequestError("backend unavailable (timeout)") from exc
        except httpx.TransportError as exc:
            raise APIRequestError(f"backend unavailable ({type(exc).__name__})") from exc

    async def _get(
        self,
        path: str,
        params: _Params | None = None,
        *,
        forwarded_for: str | None = None,
    ) -> Any:
        """GET *path* with auth, refreshing the guest token once on 401.

        The MCP server is long-lived but guest tokens are short-lived, so a cached
        token eventually expires. On 401 we re-acquire once and retry; the refresh
        itself is serialized through ``_refresh_token`` so N concurrent calls that all
        401 on the same stale token trigger a single guest-token POST, not N.
        """
        await self._ensure_token()
        used_token = self.token
        resp = await self._send(path, params, forwarded_for)
        if resp.status_code == 401:
            await self._refresh_token(used_token)
            resp = await self._send(path, params, forwarded_for)
        _raise_for_api_error(resp)
        return resp.json()

    async def search(
        self,
        q: str,
        *,
        mode: str,
        topic: str | None = None,
        source: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 10,
        forwarded_for: str | None = None,
    ) -> list[dict[str, Any]]:
        params: _Params = {"q": q, "limit": limit}
        for key, value in (
            ("topic", topic),
            ("source", source),
            ("date_from", date_from),
            ("date_to", date_to),
        ):
            if value:
                params[key] = value
        if mode == "semantic":
            params["recent_first"] = "false"
            return await self._get("/api/search/semantic", params, forwarded_for=forwarded_for)
        return await self._get("/api/search", params, forwarded_for=forwarded_for)

    async def get_item(self, item_id: str, *, forwarded_for: str | None = None) -> dict[str, Any]:
        return await self._get(f"/api/items/{item_id}", forwarded_for=forwarded_for)

    async def find_similar(
        self, item_id: str, *, limit: int = 5, forwarded_for: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._get(
            f"/api/items/{item_id}/similar", {"limit": limit}, forwarded_for=forwarded_for
        )

    async def topic_trend(
        self,
        q: str,
        *,
        method: str,
        granularity: str,
        since: str | None = None,
        max_distance: float | None = None,
        forwarded_for: str | None = None,
    ) -> dict[str, Any]:
        params: _Params = {"q": q, "method": method, "granularity": granularity}
        if since:
            params["since"] = since
        if max_distance is not None:
            params["max_distance"] = max_distance
        return await self._get("/api/stats/trend", params, forwarded_for=forwarded_for)

    async def get_top(
        self,
        *,
        days: int = 7,
        topic: str | None = None,
        source: str | None = None,
        limit: int = 10,
        forwarded_for: str | None = None,
    ) -> list[dict[str, Any]]:
        params: _Params = {"days": days, "limit": limit}
        if topic:
            params["topic"] = topic
        if source:
            params["source"] = source
        return await self._get("/api/items/top", params, forwarded_for=forwarded_for)
