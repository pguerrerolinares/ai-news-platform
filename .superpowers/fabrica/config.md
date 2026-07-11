# Config de fábrica — ai-news-platform

> Seam por proyecto (spec §4.6). VERSIONADO. El protocolo del skill es idéntico
> entre proyectos; este fichero es todo lo que cambia. Lo gatea Paul como
> cualquier rama.

## Fuentes de criterio escrito (para la regla de la cita)
- `CLAUDE.md` (convenciones + 8 principios de ingeniería)
- `AGENTS.md` (arquitectura, endpoints, schema, risk tracks)
- `.superpowers/fabrica/backlog-2026-07-11.md` (criterios de aceptación por item,
  derivados de la auditoría 2026-07-11 y decisiones de Paul en esa sesión)

## Roadmap / backlog
- `.superpowers/fabrica/backlog-2026-07-11.md` — items 1→7 en orden.

## Oráculos (comando literal + qué prueba)
- suite backend: `pytest tests/unit/ -x --timeout=30 -q` (último run verde:
  2026-07-11, 1123 passed) + `ruff check . && ruff format --check . && pyright .`
  (verdes 2026-07-11)
- suite completa (pre-package): `pytest tests/ -x --timeout=30 -q` (incluye
  integration + security; e2e requiere build en frontend/dist)
- frontend: `npm --prefix frontend run build` (tsc -b + vite) y
  `npm --prefix frontend run lint`
- migraciones (item 6): `alembic upgrade head && alembic check` contra la DB
  docker local (`docker compose up db -d`)
- evals: no aplica (no hay gold sets en esta campaña; el único item de diseño
  usa spec-first + suite como oráculo)

## Corpus negativos
- No aplica en esta campaña.

## Presupuesto (unidades de spec §7: dispatches por modelo + horas de reloj)
- reserva fable: ≤ 6 dispatches/noche (spec item 6, adjudicaciones, reviews de rama)
- cap at-risk por item: ≤ 8 dispatches sonnet o 2h
- cap retries por eval: 2 (default spec §8)

## Clases de decisión pre-autorizadas (spec §5.1)
- Naming/ubicación de tests nuevos siguiendo convenciones existentes de tests/.
- Elección de mensajes de log/métricas Prometheus (nombres siguiendo el patrón
  existente en src/core/metrics.py).
- Detalles de UI al retirar entradas de nav (espaciado, orden de items restantes).
