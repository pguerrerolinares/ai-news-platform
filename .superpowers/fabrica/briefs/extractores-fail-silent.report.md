# Informe — extractores-fail-silent

## Estado
Completado. Rama `fabrica/extractores-fail-silent`, worktree `.worktrees/extractores-fail-silent`.

## Commit
`52844fb fix(pipeline): feed per-source failures into circuit breaker + metric [Track B]`

## Cambio
- `src/pipeline/stages/extract.py`: `run_extraction` recibe `circuit_breaker: CircuitBreaker | None = None` (parámetro explícito, sin singleton nuevo). Por cada extractor: si el breaker ya está abierto para esa fuente, se salta sin llamar a `extract()`; si extrae bien, `record_success(source)`; si lanza, `record_failure(source)` + incrementa `extractor_errors_total.labels(source=...)` (métrica ya existente en `src/core/metrics.py:51-55`, solo la reuso, no invento una nueva).
- `src/pipeline/pipeline.py`: `run_pipeline` recibe `circuit_breaker` y lo pasa a `run_extraction`.
- `src/pipeline/scheduler.py`: `run_scheduled_pipeline` pasa su singleton `_circuit_breaker` como parámetro explícito a `run_pipeline`.

## Punto de integración elegido (skip de fuente con circuito abierto)
Dos capas, documentadas ambas en el código:
1. **Ya existente** en `src/pipeline/scheduler.py:34` — `active_sources = [s for s in sources if not _circuit_breaker.is_open(s)]`. Pese a que el brief describía esto como "a nivel de tier", el código real ya filtra **por fuente individual** (list comprehension por `s`), no todo-o-nada por tier. Confirmado leyendo el código antes de tocar nada.
2. **Añadido** en `run_extraction` (`src/pipeline/stages/extract.py`): chequeo `circuit_breaker.is_open(source)` antes de invocar `extractor.extract()`. Es defensa en profundidad para cualquier caller que no pase por el scheduler (llamadas directas a `run_pipeline`/`run_extraction`, tests, CLI futura) — no es una capa nueva, es el mismo breaker consultado en el punto donde ya se itera por fuente.

## Decisión no trivial: eliminé el `record_success` en bloque de `scheduler.py`
El código original hacía, tras cada `run_pipeline` exitoso:
```python
if result:
    for source in active_sources:
        _circuit_breaker.record_success(source)
```
Esto es precisamente el bug que el brief pedía arreglar, visto desde otro ángulo: `run_pipeline` devuelve `True` en cuanto hay *algún* ítem extraído y almacenado — no exige que todas las fuentes del tier hayan funcionado (`src/pipeline/pipeline.py:72-86`, el pipeline solo devuelve `False` si `all_items` está vacío). Si dentro de ese mismo run la fuente A fallaba (excepción capturada en `run_extraction`) y la fuente B funcionaba, `result=True` y este bloque llamaba `record_success("A")`, **deshaciendo** el `record_failure("A")` que la stage de extract acababa de registrar. El breaker nunca se abriría de verdad para una fuente rota mientras conviviera con al menos una fuente sana en el mismo tier.

Con el tracking por fuente ya dentro de `run_extraction`, este bloque quedaba redundante en el camino feliz y activamente dañino en el camino mixto. Lo eliminé y documenté la razón en el docstring de `run_scheduled_pipeline`. El bloque `except Exception` que sigue penalizando todas las fuentes del tier ante un fallo de infraestructura (DB/red) se dejó intacto — ese es un caso distinto (no es específico de una fuente) y ya tenía su propio comentario justificándolo.

## Tests añadidos (TDD)
- `tests/unit/test_stage_extract.py::TestRunExtractionCircuitBreaker` (6 tests): fallo registrado solo para la fuente que falla; éxito resetea contador; 3 fallos consecutivos abren el circuito (usa umbrales reales del breaker, sin números nuevos); circuito abierto salta la extracción sin llamar `extract()`; comportamiento sin breaker (compatibilidad); incremento de `extractor_errors_total`.
- `tests/unit/test_scheduler.py`: actualicé las 2 aserciones `assert_called_once_with` para incluir `circuit_breaker=_circuit_breaker`, y añadí `TestSchedulerDoesNotBlanketResetBreaker` — regresión que reproduce el bug original (fallo previo de una fuente + pipeline exitoso) y confirma que ya no se resetea.

## Oráculos (tails)
```
$ ruff check .
All checks passed!

$ ruff format --check .
204 files already formatted

$ pyright .   (con --pythonpath apuntando al venv del repo principal, symlink no aplica en worktree)
0 errors, 506 warnings, 0 informations

$ pytest tests/unit/ -x --timeout=30 -q
1133 passed, 56 warnings in 13.32s
```
(1123 base + 10 nuevos = 1133, correcto)

## Self code-review
Diff repasado (`git diff` completo, 5 archivos, +188/-11): sin abstracciones nuevas, breaker inyectado por parámetro (regla del brief respetada), métrica reutilizada, comportamiento existente preservado (una fuente rota no tumba el run), docstrings actualizados donde cambia el contrato (`run_pipeline`, `run_extraction`, `run_scheduled_pipeline`).

## Notas de entorno
El worktree no tenía `.venv` propio; usé el `.venv` del repo principal con `PYTHONPATH` apuntando al worktree para que el código bajo test se resuelva desde ahí y no desde el editable-install que apunta al repo principal (`.venv/lib/python3.12/site-packages/_editable_impl_ai_news_platform.pth` apunta a la ruta del repo principal, no del worktree).
