# ADR-005: Risk-Based Autonomy for Agent Development

## Status: Accepted
## Date: 2026-02-17

## Context
This project is developed 100% by AI agents. We need a framework that balances speed (autonomous agent work) with safety (human oversight for risky changes). Inspired by Zeroclaw's risk tracks.

## Decision
Three-track risk classification system for all changes:

- **Track A (Low Risk)**: Docs, tests, isolated refactors, config changes. CI passes -> auto-deploy.
- **Track B (Medium Risk)**: New extractors, API changes, frontend features. CI + integration tests -> auto-deploy.
- **Track C (High Risk)**: DB migrations, security changes, pipeline core, CI/CD changes. CI + human review via PR.

## Consequences
**Pros:**
- Fast iteration on low-risk changes (no PR bottleneck)
- Human oversight where it matters most (DB, security, core pipeline)
- Clear classification criteria for agents
- Rollback-first design: every deploy can be reverted

**Cons:**
- Requires discipline in risk classification
- Track A/B auto-deploy means bugs can reach production faster
- Relies on CI quality (tests must be comprehensive)

**Mitigations:**
- Automated health checks post-deploy with rollback
- Telegram alerts on any failure
- Docker images tagged with SHA for easy rollback
- Alembic migrations always have functional downgrade()
