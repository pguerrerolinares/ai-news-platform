# Review-package — rama `fabrica/sanear-error-message-admin`

> Veredicto de Paul AQUÍ: appendear `GATE: MERGED` o `GATE: RECHAZADA — <motivo>`.

## Qué se hizo
`/api/admin/pipeline-runs` es público (guest tokens) pero servía `error_message` crudo
(hasta 500 chars: paths internos, fragmentos de traceback). Ahora se sanea AL SERVIR
(la DB conserva el detalle completo para debugging): primera línea, paths absolutos
→ `[path]`, cap 120 chars. Helper `_sanitize_error_message` local a la ruta, sin capas
nuevas. Test existente que afirmaba la exposición as-is reescrito para validar el saneo.
Commit: `557d63b` — `fix(api): sanitize pipeline error_message exposed via public admin routes [Track B]`

## Spec aplicada
`.superpowers/fabrica/briefs/sanear-error-message-admin.md` (item 5 del backlog 2026-07-11)

## Base de stacking
origin/main (60d6ba9)

## Resultados de oráculo
- `pytest tests/unit/ -x --timeout=30 -q` → 1126 passed (ejecutor Y padre, runs independientes)
- `ruff check . && ruff format --check .` → verde (ejecutor)
- `pyright .` → 0 errors (ejecutor)

## Reviews
- Self-review del ejecutor: sin findings.
- Review de rama (orquestador fable): diff correcto y mínimo. Nit no bloqueante: el
  docstring menciona "hosts/IPs" pero la regex solo redacta paths (URLs internas quedan
  parcialmente redactadas desde su primer `/`); aceptable para la superficie real.
- Decisión del ejecutor bien tomada: no parsear "tipo de excepción" desde un string libre
  (la DB guarda `str(exc)` sin clase) — simplificación anti-over-engineering, documentada.

## Verdicts del adjudicador
Ninguno — el punto de saneo (al servir) venía pre-resuelto en el brief.

## Instrucción de merge
`git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/sanear-error-message-admin`

<!-- GATE: (lo escribe Paul) -->
