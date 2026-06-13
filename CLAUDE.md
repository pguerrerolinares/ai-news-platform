# CLAUDE.md — AI News Platform Coding Conventions

## Language & Style
- **Code and comments**: English
- **Backend user-facing text** (LLM summaries): Spanish
- **Frontend text**: English (all UI labels, buttons, errors via i18n)
- **Type hints**: Required everywhere. Use `from __future__ import annotations` in every module.
- **Docstrings**: Public APIs only. Google style, concise.
- **Line length**: 100 characters (configured in ruff)
- **Python version**: 3.12+

## Naming Conventions
- **Modules**: `snake_case` (e.g., `hackernews.py`, `llm_classifier.py`)
- **Classes**: `PascalCase` (e.g., `HackerNewsExtractor`)
- **Implementations**: `<Name>Extractor`, `<Name>Classifier`, `<Name>Validator`, `<Name>Notifier`
- **Interfaces**: `Base<Type>` (e.g., `BaseExtractor`, `BaseClassifier`)
- **Constants**: `UPPER_SNAKE_CASE`
- **Functions/methods**: `snake_case`

## Architecture Principles
- **Async by default**: httpx for HTTP, asyncpg for DB, SQLAlchemy async sessions
- **Interface-based**: Every new component implements an ABC and is registered in its module's `__init__.py`
- **Open/Closed**: Extend via new implementations, NOT by modifying existing ones
- **Fail Fast**: Raise exceptions early. Never silently catch and continue.

## Quality Gates
- **Tests**: Every module gets tests. Min 80% coverage.
- **Pre-push**: `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`
- **Conventional commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `ci:`
- **Risk tracks in commits**: Add `[Track A]`, `[Track B]`, or `[Track C]` to commit messages for significant changes

## Security (Deny-by-Default)
- SSRF protection on ALL external URL fetches (check for private IP ranges)
- Never commit secrets (`.env` in `.gitignore`)
- bandit scan in CI, no exceptions
- Use neutral/synthetic data in tests

## Observability
- structlog with `correlation_id` on every log entry
- Prometheus metric on every pipeline step
- Pipeline run stats (per-stage counts, failures, duration) persisted to the `pipeline_runs` table, queryable via the admin API (audit, freshness, pipeline-runs)

## Dependencies
- Pin with `~=` in `pyproject.toml`
- Justify new dependencies in commit message
- Prefer stdlib over external packages when reasonable

## Documentation (Required on Every Change)
1. Update `AGENTS.md` if file map, architecture, endpoints, or schema changed
2. Write ADR for any architectural decision
3. Mark completed tasks in `docs/plans/milestone-N.md`
4. Risk classification in commit message if relevant

## 8 Engineering Principles
1. **KISS**: Direct logic, no meta-programming
2. **YAGNI**: No features/config without a concrete use case
3. **DRY + Rule of Three**: Extract only after 3 stable repetitions
4. **SRP + ISP**: One responsibility per module, extend via interfaces
5. **Fail Fast + Explicit Errors**: Never silence errors or expand permissions
6. **Secure by Default + Least Privilege**: Deny-by-default
7. **Determinism + Reproducibility**: Deterministic behavior for reliable CI
8. **Reversibility + Rollback-First**: Every change easy to revert
