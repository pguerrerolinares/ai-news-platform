# ADR-003: LLM classifier en kimi-k2.6 sin thinking + errores de config/cuenta fallan el run

**Date**: 2026-09-13
**Status**: Accepted
**Track**: B (medium risk — changes classification output volume and pipeline failure semantics)

## Context

Between 2026-08-22 and 2026-09-12 the pipeline stored 0-1 items/day instead of ~120, with no alert:

- **2026-08-22 → 08-27**: Moonshot returned `429 exceeded_current_quota_error` ("account suspended due to insufficient balance"). 759 retry-exhausted calls.
- **2026-08-31 09:39 UTC → 09-12**: Moonshot retired `kimi-k2.5` and the `moonshot-v1` series on 2026-08-31 16:00 (Beijing); the `kimi-latest` alias died with them (`404 Not found the model kimi-latest`). 2,239 calls.

Both failures were caught by the broad `except Exception` in `LLMClassifier.classify` and silently degraded to `KeywordClassifier`, whose relevance never reaches the threshold. Every pipeline run still reported `success`.

The replacement models reject the hardcoded `temperature=0.1`: `kimi-k2.6` accepts only `0.6` (thinking disabled) or `1.0` (thinking enabled); `kimi-k3` only `1.0`, with thinking always on. Pricing per 1M tokens (input/output): `kimi-k2.6` $0.95/$4.00, `kimi-k3` $3.00/$15.00.

## Benchmark (2026-09-13)

Production prompt and parser, 166 fresh items (72h, blind hand labels: 19 news / 42 not news / 105 ambiguous) + 62 items `kimi-latest` accepted in Aug. 2 runs per config except `k3 max`. Measured spend matched the projection ($1.37).

At `MIN_RELEVANCE_SCORE=0.8`:

| | k2.6 no-thinking | k3 low | k3 max | gpt-5.4-mini |
|---|---|---|---|---|
| Recall on news (19) | 0.71 | 0.68 | 0.68 | 0.61 |
| False positives (42) | 1 | 0 | 0 | 7.5 |
| Topic agreement vs kimi-latest | 75% | 92% | 93% | 68% |
| Run-to-run consistency | 0.83 | 0.91 | — | 0.76 |
| Latency p50 / p95 per batch | 8.4s / 10.5s | 15s / 28s | 59s / 81s | 3.3s / 3.8s |
| Projected cost (1,300 items/day) | $0.26/day | $1.30/day | $4.51/day | n/a |

`kimi-k2.6` with thinking enabled took ~100s and ~4.5k reasoning tokens per batch; discarded.
Simulating the full classification stage (keyword pre-filter + LLM), `k2.6 no-thinking` accepts 23-28% at 0.8 vs 42-47% at 0.75; `kimi-latest` accepted 31% (Aug 10-21).

Limits: single annotator, n=61 binary labels (1-2 item differences are noise); one day of data; no `github_search`/`webscraper` items.

## Decision

- Default `OPENAI_MODEL=kimi-k2.6`, `OPENAI_TEMPERATURE=0.6`, `OPENAI_EXTRA_BODY={"thinking": {"type": "disabled"}}`. Temperature and extra body are settings, used by both the classifier and the RAG chat.
- Default `MIN_RELEVANCE_SCORE=0.8` to keep the accepted volume near the pre-outage level.
- 4xx API errors and quota 429s are **config/account errors**: not retried, not sent to the keyword fallback — they propagate, so the run is persisted as `status=error` with `error_message`. The fallback remains only for transient errors (timeouts, connection errors, 5xx, rate limits after retries).

`kimi-k3 low` is the upgrade path if topic accuracy matters more than ~5x cost (only env changes needed: `OPENAI_MODEL=kimi-k3`, `OPENAI_TEMPERATURE=1.0`, `OPENAI_EXTRA_BODY={"reasoning_effort": "low"}`).

## Consequences

- A retired model, invalid params, bad key or empty balance now make every pipeline run fail visibly (`pipeline_runs.status=error`) instead of degrading silently. The scheduler also records circuit-breaker failures for the run's sources, pausing them for the cooldown.
- There is still no push alert (no notifier exists); detection relies on `pipeline_runs` / admin API / Prometheus `pipeline_runs_total{status="error"}`.
- Rollback: revert the commit, or set `OPENAI_MODEL`/`OPENAI_TEMPERATURE`/`OPENAI_EXTRA_BODY`/`MIN_RELEVANCE_SCORE` via env.
