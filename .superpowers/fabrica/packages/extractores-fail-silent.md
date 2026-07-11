# Review-package — rama `fabrica/extractores-fail-silent`

> Veredicto de Paul AQUÍ: appendear `GATE: MERGED` o `GATE: RECHAZADA — <motivo>`.

## Qué se hizo
Los fallos de extractores individuales se tragaban (`[]`) sin alimentar el circuit
breaker. Ahora `run_extraction` recibe el breaker como PARÁMETRO explícito y por fuente:
fallo → `record_failure` + métrica `extractor_errors_total` (reutilizada, no nueva);
éxito → `record_success`; circuito abierto → skip sin llamar al extractor. Una fuente
rota sigue sin tumbar a las demás. 5 ficheros, +188/-11, 10 tests nuevos (TDD).

**Hallazgo extra del ejecutor (el plato fuerte)**: el scheduler hacía `record_success`
EN BLOQUE para todas las fuentes del tier cuando `run_pipeline` devolvía True — y True
solo exige que ALGUNA fuente extrajera. Eso deshacía el `record_failure` de la fuente
rota en el mismo run: el breaker nunca podía abrirse para una fuente rota conviviendo
con una sana. Bloque eliminado con test de regresión que reproduce el caso mixto. El
`except` que penaliza el tier entero ante fallo de infraestructura se conserva (caso
distinto, ya justificado en su comentario).
Commit: `52844fb` — `fix(pipeline): feed per-source failures into circuit breaker + metric [Track B]`

## Spec aplicada
`.superpowers/fabrica/briefs/extractores-fail-silent.md` (item 2 del backlog; mecanismo
de inyección fijado post-blindspot: parámetro explícito > singleton)

## Base de stacking
origin/main (60d6ba9)

## Resultados de oráculo
- `pytest tests/unit/ -x --timeout=30 -q` → 1133 passed (1123 base + 10 nuevos; ejecutor Y padre, independientes)
- `ruff check . && ruff format --check .` → verde (ejecutor)
- `pyright .` → 0 errors (ejecutor)

## Reviews
- Self-review del ejecutor: sin findings; contrato documentado en docstrings.
- Review de rama (orquestador fable): diff leído entero — inyección por parámetro
  correcta en la cadena scheduler→run_pipeline→run_extraction; el skip en la stage es
  defensa en profundidad razonable, no capa nueva; la corrección del blanket-reset está
  bien argumentada con cita de código (`pipeline.py:72-86`) y cubierta por regresión.
  Nota para el gate: el informe corrige un supuesto del brief — el scheduler YA filtraba
  por fuente individual, no por tier; el ejecutor lo verificó leyendo antes de tocar.

## Verdicts del adjudicador
Ninguno formal. La decisión "eliminar el record_success en bloque" está adjudicada por
cita de código real + test de regresión (informe §Decisión no trivial), revisada y
aceptada por el orquestador. Es el punto a spot-auditar en este package.

## Instrucción de merge
`git -C /home/paul/Documentos/proyectos/backend/ai-news-platform merge --no-ff fabrica/extractores-fail-silent`

<!-- GATE: (lo escribe Paul) -->
