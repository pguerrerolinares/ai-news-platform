# Brief — extractores-fail-silent

## Dónde encaja
Campaña post-auditoría. Hallazgo: `src/pipeline/stages/extract.py:45-51` — cualquier excepción de un extractor se loguea y se convierte en `[]`, indistinguible de "no había nada nuevo". El circuit breaker (`src/pipeline/circuit_breaker.py`) solo se alimenta a nivel de tier desde `scheduler.py`, nunca por fuente. Un extractor roto (selector HTML cambiado) puede morir para siempre sin señal. Contradice CLAUDE.md "Fail Fast: never silently catch and continue".

## Worktree y rama
- Trabaja en `/home/paul/Documentos/proyectos/backend/ai-news-platform/.worktrees/extractores-fail-silent` (rama `fabrica/extractores-fail-silent` desde origin/main). Usa `git -C`, nunca `cd &&`.
- PROHIBIDO: push, merge, tocar main. Solo commits locales en tu rama.
- Necesitarás el venv: crea uno propio en el worktree o usa `pip install -e ".[api,pipeline,dev]"` — mira cómo está montado `.venv` en el repo principal y replica lo mínimo. La DB de tests no hace falta para unit.

## Tarea (TDD: test primero)
1. Lee ANTES de escribir: `src/pipeline/stages/extract.py`, `src/pipeline/circuit_breaker.py`, `src/pipeline/scheduler.py` (cómo alimenta hoy el breaker), `src/core/metrics.py` (patrón de métricas), y los tests existentes de extract/circuit breaker en `tests/unit/`.
2. Cambio: cuando un extractor individual lanza excepción en la stage de extract, además del log:
   - registrar el fallo POR FUENTE en el circuit breaker (reusar el existente). Resolución de ambigüedad: si el breaker se instancia en scheduler y no llega a la stage, pásalo como PARÁMETRO explícito (constructor de la stage o argumento de `run_extraction`), siguiendo cómo la stage recibe ya sus otras dependencias. Regla: parámetro explícito > singleton de módulo > variable global. No inventes una capa nueva ni un registry.
   - registrar éxito por fuente cuando extrae bien (para que el breaker se resetee),
   - emitir métrica Prometheus de fallo por fuente siguiendo el patrón de `src/core/metrics.py`,
   - respetar el comportamiento existente: las demás fuentes siguen extrayendo (el fallo de una no tumba el run).
3. Con el breaker abierto para una fuente, la stage debe saltársela (skip) hasta el cooldown — si eso ya lo hace el scheduler por tier, decide el punto de integración más simple y DOCUMÉNTALO en el informe con cita del código.

## Criterio de aceptación (backlog item 2)
- Test unit: extractor que lanza → breaker registra fallo para ESA fuente y el resto sigue; 3 fallos → circuito abierto (usa los umbrales existentes del breaker, no números nuevos).
- `pytest tests/unit/ -x --timeout=30 -q` completo en verde (1123 tests base + los tuyos).
- `ruff check . && ruff format --check . && pyright .` en verde.

## Restricciones
- No over-engineering: nada de event buses ni abstracciones nuevas; reusar el breaker tal cual.
- Fail Fast del CLAUDE.md aplica al DISEÑO (señal visible), no a tumbar el pipeline: una fuente rota no debe parar las demás.
- Type hints + `from __future__ import annotations`. Async by default.

## Quality gate (obligatorio antes de reportar)
- Oráculos arriba en verde (pega tails en el informe).
- Self code-review del diff antes de reportar.
- Commit atómico: `fix(pipeline): feed per-source failures into circuit breaker + metric [Track B]`.

## Informe
Escribe `.superpowers/fabrica/briefs/extractores-fail-silent.report.md` en el repo PRINCIPAL: estado, commit, salida de oráculos, punto de integración elegido con cita, decisiones. Mensaje final: 2 líneas.

## Memory packet (read_note solo si hace falta; proyecto wisdom-paul)
- [[Paul - perfil de trabajo]] — no over-engineering, pragmatismo, trade-offs explícitos
- [[doctrina-agentes]]
- [[desarrollo-agentico]]
