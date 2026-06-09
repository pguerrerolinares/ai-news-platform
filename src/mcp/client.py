"""HTTP client for the AI News Platform API."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx


class APIClient:
    """Synchronous client that wraps the FastAPI REST API."""

    def __init__(self, base_url: str = "http://localhost:8000", token: str = ""):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=30)
        self.token = token or self._acquire_guest_token()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> APIClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _acquire_guest_token(self) -> str:
        resp = self._http.post("/api/auth/guest")
        if resp.status_code != 200:
            raise RuntimeError(f"MCP guest token acquisition failed: {resp.status_code}")
        return resp.json()["access_token"]

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def search(
        self,
        q: str,
        topic: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        params: dict[str, str | int] = {"q": q, "limit": limit}
        if topic:
            params["topic"] = topic
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        resp = self._http.get("/api/search", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def semantic_search(self, q: str, limit: int = 10) -> list[dict]:
        params: dict[str, str | int] = {"q": q, "limit": limit}
        resp = self._http.get("/api/search/semantic", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def get_latest(self, topic: str | None = None, limit: int = 10) -> list[dict]:
        params: dict[str, str | int] = {"limit": limit}
        if topic:
            params["topic"] = topic
        resp = self._http.get("/api/items/today", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def get_trending(self) -> list[dict]:
        params = {"trending": "true", "limit": 20}
        resp = self._http.get("/api/items", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def get_briefing(self, date: str | None = None) -> dict:
        if not date:
            date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        resp = self._http.get(f"/api/briefings/{date}", headers=self._headers)
        resp.raise_for_status()
        return resp.json()
