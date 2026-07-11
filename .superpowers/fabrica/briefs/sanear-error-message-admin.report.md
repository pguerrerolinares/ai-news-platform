# Informe — sanear-error-message-admin

## Estado
Completado. Rama `fabrica/sanear-error-message-admin`, worktree `.worktrees/sanear-error-message-admin`. Sin push/merge (según lo pedido).

## Commit
`557d63b` — `fix(api): sanitize pipeline error_message exposed via public admin routes [Track B]`

## Punto de saneo elegido
(a) Al SERVIR, como pedía el brief. Se añadió un helper `_sanitize_error_message` en `src/api/routes/admin.py` que se aplica en `admin_pipeline_runs` justo antes de construir `PipelineRunResponse`. La DB conserva el `error_message` completo (hasta 500 chars, escrito en `src/pipeline/pipeline.py:201`) intacto para debugging interno; el saneo solo afecta la respuesta pública.

Saneo mínimo: toma la primera línea del mensaje (descarta tracebacks multilínea), redacta rutas absolutas Unix/Windows con una regex (`(?:[A-Za-z]:\\|/)[\w./\\-]+` → `[path]`) y trunca a 120 chars con elipsis. No se intentó recuperar el tipo de excepción (el string almacenado es solo `str(exc)`, sin el nombre de la clase), así que la opción "tipo + primera línea" del brief se simplificó a "primera línea saneada" — evita over-engineering de parsear/reconstruir el tipo desde un string libre.

## Tests
- Se actualizó el test existente `test_error_message_exposed_for_debugging` (que afirmaba explícitamente exposición as-is, contradecía el objetivo) → renombrado a `test_error_message_is_sanitized_for_public_response`, con mensaje multilínea + path interno; valida que el path no aparece verbatim, no hay `\n`, y `len <= 120`.
- Actualizado el docstring del módulo de test para reflejar el nuevo comportamiento.

## Oráculos (en el worktree, venv propio creado con `uv venv` + `uv pip install -e ".[api,pipeline,dev]"`)
- `pytest tests/unit/ -x --timeout=30 -q` → **1126 passed**.
- `ruff check .` → **All checks passed**.
- `ruff format --check .` → **204 files already formatted**.
- `pyright .` (proyecto completo, respeta venv) → **0 errors**, 496 warnings (preexistentes, no relacionados con el cambio).
