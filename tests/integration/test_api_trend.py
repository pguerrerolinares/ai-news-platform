"""Integration tests for GET /api/stats/trend against real PostgreSQL."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import AsyncMock

import pytest

from src.rag.embeddings import EmbeddingService
from tests.integration.conftest import seed_embedding, seed_news_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.fixture(autouse=True)
def _reset_stats_limiter():
    from src.api.routes.stats import limiter

    limiter.reset()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _noon(d: date) -> datetime:
    return datetime.combine(d, time(12), tzinfo=UTC)


def _unit_vector_at_distance(dist: float) -> list[float]:
    """A 512-dim unit vector whose cosine distance from [1, 0, 0, ...] is exactly `dist`."""
    cos_theta = 1 - dist
    sin_theta = math.sqrt(1 - cos_theta * cos_theta)
    return [cos_theta, sin_theta] + [0.0] * 510


_QUERY_VECTOR = [1.0] + [0.0] * 511


class TestTrendKeyword:
    async def test_counts_by_week_with_empty_buckets_and_share(
        self, client, db_session, auth_headers
    ):
        this_week = _monday(datetime.now(tz=UTC).date())
        middle_week = this_week - timedelta(days=7)
        first_week = this_week - timedelta(days=14)
        await seed_news_item(
            db_session,
            title="Speculative decoding speeds up inference",
            source="arxiv",
            published_at=_noon(this_week),
        )
        await seed_news_item(
            db_session,
            title="Speculative decoding lands in vLLM",
            source="github",
            published_at=_noon(this_week),
        )
        await seed_news_item(
            db_session,
            title="Unrelated robotics news",
            source="rss",
            published_at=_noon(this_week),
        )
        await seed_news_item(
            db_session,
            title="Speculative decoding survey",
            source="arxiv",
            published_at=_noon(first_week),
        )

        resp = await client.get(
            "/api/stats/trend",
            params={
                "q": "speculative decoding",
                "granularity": "week",
                "since": first_week.isoformat(),
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["method"] == "keyword"
        assert body["max_distance"] is None
        assert body["distance_edges"] is None
        by_bucket = {b["bucket"]: b for b in body["buckets"]}
        assert list(by_bucket) == [
            first_week.isoformat(),
            middle_week.isoformat(),
            this_week.isoformat(),
        ]
        current = by_bucket[this_week.isoformat()]
        assert current["count"] == 2
        assert current["by_source"] == {"arxiv": 1, "github": 1}
        assert current["by_distance"] is None
        assert current["total_in_bucket"] == 3
        assert current["share"] == pytest.approx(2 / 3, abs=1e-4)
        empty = by_bucket[middle_week.isoformat()]
        assert (empty["count"], empty["total_in_bucket"], empty["share"]) == (0, 0, 0.0)

    async def test_rejects_since_older_than_24_months(self, client, auth_headers):
        too_old = datetime.now(tz=UTC).date() - timedelta(days=731)

        resp = await client.get(
            "/api/stats/trend",
            params={"q": "agents", "since": too_old.isoformat()},
            headers=auth_headers,
        )

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_out_of_range_max_distance_is_422_even_in_keyword(self, client, auth_headers):
        resp = await client.get(
            "/api/stats/trend",
            params={"q": "agents", "max_distance": 0.7},
            headers=auth_headers,
        )

        assert resp.status_code == 422


class TestTrendSemantic:
    async def test_by_distance_is_cumulative_over_three_items(
        self, client, db_session, auth_headers, monkeypatch
    ):
        """Decision's worked example: items at cosine distance 0.10 / 0.38 / 0.47 from
        the query -> by_distance == {"0.30":1,"0.35":1,"0.40":2,"0.45":2,"0.50":3};
        count==2 at the default max_distance=0.40.
        """
        week = _monday(datetime.now(tz=UTC).date())
        near = await seed_news_item(
            db_session, title="Near", source="arxiv", published_at=_noon(week)
        )
        mid = await seed_news_item(
            db_session, title="Mid", source="github", published_at=_noon(week)
        )
        far = await seed_news_item(
            db_session, title="Far", source="hackernews", published_at=_noon(week)
        )
        await seed_news_item(
            db_session, title="No embedding", source="rss", published_at=_noon(week)
        )
        await seed_embedding(db_session, near, vector=_unit_vector_at_distance(0.10))
        await seed_embedding(db_session, mid, vector=_unit_vector_at_distance(0.38))
        await seed_embedding(db_session, far, vector=_unit_vector_at_distance(0.47))
        fake = AsyncMock(spec=EmbeddingService)
        fake.embed_text.return_value = _QUERY_VECTOR
        monkeypatch.setattr("src.api.routes.stats._embedding_service", fake)

        resp = await client.get(
            "/api/stats/trend",
            params={
                "q": "anything",
                "method": "semantic",
                "granularity": "week",
                "since": week.isoformat(),
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_distance"] == 0.40
        assert body["distance_edges"] == [0.30, 0.35, 0.40, 0.45, 0.50]
        assert len(body["buckets"]) == 1
        bucket = body["buckets"][0]
        assert bucket["bucket"] == week.isoformat()
        assert bucket["count"] == 2
        assert bucket["by_source"] == {"arxiv": 1, "github": 1}
        assert bucket["by_distance"] == {
            "0.30": 1,
            "0.35": 1,
            "0.40": 2,
            "0.45": 2,
            "0.50": 3,
        }
        assert bucket["total_in_bucket"] == 3  # the rss item has no embedding

        resp = await client.get(
            "/api/stats/trend",
            params={
                "q": "anything",
                "method": "semantic",
                "granularity": "week",
                "since": week.isoformat(),
                "max_distance": 0.5,
            },
            headers=auth_headers,
        )
        bucket = resp.json()["buckets"][0]
        assert bucket["count"] == 3
        assert bucket["by_source"] == {"arxiv": 1, "github": 1, "hackernews": 1}

    async def test_max_distance_out_of_range_is_422(self, client, auth_headers):
        # max_distance is validated by Query(ge=..., le=...), so this goes through
        # FastAPI's own RequestValidationError handler (body {"detail": [...]}, a
        # list), not the APIError envelope — same convention as every other
        # Query-driven 422 in this codebase (see test_stats_api.py, test_search_api.py)
        # and the shape the MCP client's _validation_detail expects.
        resp = await client.get(
            "/api/stats/trend",
            params={"q": "agents", "method": "semantic", "max_distance": 0.7},
            headers=auth_headers,
        )

        assert resp.status_code == 422
        assert isinstance(resp.json()["detail"], list)

    async def test_embedding_failure_is_503_not_an_empty_series(
        self, client, auth_headers, monkeypatch
    ):
        fake = AsyncMock(spec=EmbeddingService)
        fake.embed_text.side_effect = RuntimeError("no api key")
        monkeypatch.setattr("src.api.routes.stats._embedding_service", fake)

        resp = await client.get(
            "/api/stats/trend",
            params={"q": "agents", "method": "semantic"},
            headers=auth_headers,
        )

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "EMBEDDING_UNAVAILABLE"
