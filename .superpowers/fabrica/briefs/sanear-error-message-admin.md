# Brief — sanear-error-message-admin

## Dónde encaja
Campaña post-auditoría. La API `/api/admin/*` es pública por decisión (guest tokens); pero `error_message` en las respuestas de pipeline-runs expone hasta 500 chars de excepción interna (paths, URLs internas, detalles de stack) a cualquier anónimo. Referencia: `src/api/routes/admin.py` (~línea 190, `error_message=r.error_message`; schema en ~línea 65).

## Worktree y rama
- `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/sanear-error-message-admin` (rama `fabrica/sanear-error-message-admin` desde origin/main). Usa `git -C`, nunca `cd &&`.
- PROHIBIDO: push, merge, tocar main. Venv: instala `pip install -e ".[api,pipeline,dev]"` en el worktree si hace falta.

## Tarea (TDD)
1. Lee `src/api/routes/admin.py` entero, dónde se ESCRIBE `error_message` (pipeline: busca quién persiste PipelineRun.error_message) y los tests existentes de admin en `tests/unit/`.
2. Decide el punto de saneo y justifícalo: (a) al SERVIR (la ruta trunca/sanea antes de responder — la DB conserva el detalle completo para debugging interno) o (b) al ESCRIBIR. Preferencia del diseño: (a), porque la DB es tuya y el detalle interno es útil; la frontera pública es la API. Si ves razón fuerte para (b), documéntala.
3. Saneo mínimo sin over-engineering: exponer solo tipo de excepción + primera línea corta (p.ej. cap 120 chars), sin paths absolutos ni tracebacks. Un helper pequeño en el módulo de la ruta basta; nada de capas nuevas.

## Criterio de aceptación (backlog item 5)
- Test unit: un PipelineRun con error_message conteniendo un path interno (`/home/...`) y varias líneas → la respuesta del endpoint NO contiene el path verbatim ni pasa de ~120 chars.
- `pytest tests/unit/ -x --timeout=30 -q` en verde; `ruff check . && ruff format --check . && pyright .` en verde.

## Quality gate
- Oráculos en verde (tails). Self code-review. Type hints + future annotations.
- Commit: `fix(api): sanitize pipeline error_message exposed via public admin routes [Track B]`.

## Informe
`.superpowers/fabrica/briefs/sanear-error-message-admin.report.md` en el repo PRINCIPAL: estado, commit, oráculos, punto de saneo elegido. Mensaje final: 2 líneas.

## Memory packet (read_note solo si hace falta; wisdom-paul)
- [[Paul - perfil de trabajo]]
- [[desarrollo-agentico]]
