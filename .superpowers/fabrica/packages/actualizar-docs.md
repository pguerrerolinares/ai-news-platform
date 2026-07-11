# Review-package — rama `fabrica/actualizar-docs`

> Veredicto de Paul AQUÍ: appendear `GATE: MERGED` o `GATE: RECHAZADA — <motivo>`.
> **ORDEN DE GATE**: última — su base es `fabrica/purga-auth-muerto` (documenta su estado final).

## Qué se hizo
- **AGENTS.md** actualizado contra el código REAL del worktree (cada afirmación verificada con
  grep/pytest, no de memoria): audiencia pública guest-only, schema sin las 3 tablas de auth
  (con nota histórica de la migración 018), endpoints muertos fuera de la tabla, chat anotado
  como inaccesible a propósito, file map limpio, conteo real de tests (1050 unit), y nota
  honesta del harness e2e huérfano (19 skips, busca `web/dist` de Angular) como known issue.
- **ADR-002** `docs/adr/002-web-publica-guest-only.md`, formato exacto de ADR-001: contexto
  (auditoría 2026-07-11 + decisión de Paul), decisión, consecuencias (chat como gate de gasto
  LLM que se reactiva solo si vuelve un emisor de tokens; migración destructiva con downgrade
  de schema sin datos; dump manual opcional pre-deploy).
- docs/plans/ (sin milestone activo aplicable) y docs/runbooks/ (0 referencias operativas rotas)
  revisados, sin cambios.
Commit: `2f8bf57` — `docs: actualizar AGENTS.md + ADR web pública guest-only [Track A]`

## Spec aplicada
`.superpowers/fabrica/briefs/actualizar-docs.md` (item 7 del backlog 2026-07-11)

## Base de stacking
`fabrica/purga-auth-muerto` (profundidad acumulada 3 sobre main por necesidad documental;
se mergea la última y su diff propio son solo 2 .md)

## Resultados de oráculo
- `git diff --stat` → SOLO `AGENTS.md` + `docs/adr/002-...md` (+60/−36), cero código
- Spot-check del padre: 0 referencias vivas a endpoints muertos en AGENTS.md (las 2 restantes
  son notas históricas intencionales), ADR con formato correcto

## Reviews
- Self-review del ejecutor con verificación afirmación-por-afirmación contra código.
- Review de rama (orquestador fable): consistencia verificada por muestreo; el ADR captura
  bien el porqué del `require_auth` en chat.

## Verdicts del adjudicador
Ninguno — documental.

## Instrucción de merge (tras purga-auth-muerto)
`git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/actualizar-docs`

<!-- GATE: (lo escribe Paul) -->
