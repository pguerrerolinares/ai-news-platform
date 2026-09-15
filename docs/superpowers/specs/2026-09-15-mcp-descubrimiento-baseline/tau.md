# Pre-check (a) — calibración de τ (2026-09-15)

Etiquetado: agente independiente (sonnet), ciego (sin distancias, filas barajadas), 5 queries × top-40 vecinos por scan exacto en prod. Etiquetas en `tau-labels.tsv`.

Salida literal del script F1 del plan:

```
q0: best tau=0.3493  R=37/40  dist range 0.191-0.352
q1: best tau=0.2990  R=5/40   dist range 0.288-0.358
q2: best tau=0.3928  R=2/40   dist range 0.340-0.410
q3: best tau=0.4897  R=22/40  dist range 0.376-0.497
q4: best tau=0.4075  R=14/40  dist range 0.259-0.428
spread=0.1907 median=0.3928
STOP: global tau refuted
```

Resultado: **STOP** (spread 0.19 > 0.10). Evidencia robusta más allá del ruido de etiquetado: los rangos de distancia del top-40 dependen de la query — el vecino MÁS cercano de q3 (0.376) está más lejos que el 40º de q0 (0.352). Un τ global cuenta todo q0 (y más allá del top-40, censurado: 37/40 R) y casi nada de q3.

Limitaciones: etiquetas de un solo LLM por título; q1/q2 con pocos positivos; top-40 censura el borde de q0.

Decisión pendiente de Paul (spec §6 (a)).

## Decisión

Paul delegó la decisión en un consultor (fable) en vez de reabrir el diseño él mismo. El consultor confirmó el STOP con el análisis de `tau_analysis.py` (en este directorio: precisión@K, τ relativo `d_min+δ` con spread 0.147, separabilidad R/N por rango de distancia) sobre el mismo `tau-labels.tsv`, y descartó tanto un τ global como top-K fijo: ningún corte único separa relevantes de no relevantes entre queries, y el propio concepto de "relevante" es específico de la query, no de la distancia absoluta.

Resultado: se elimina la calibración de τ. `/api/stats/trend?method=semantic` cambia el contrato a un parámetro explícito `max_distance` (default 0.40, rango [0.20, 0.60]) y devuelve, por bucket, el conteo acumulado a 5 bandas fijas de distancia (`by_distance`: 0.30/0.35/0.40/0.45/0.50) además del conteo a `max_distance`. El consumidor (un LLM vía MCP) lee la forma de la distribución y decide la banda, en vez de que el servidor pretenda saber qué es "relevante". Contrato completo: spec `docs/superpowers/specs/2026-09-15-mcp-descubrimiento-design.md` §4.3.5 y `docs/superpowers/sdd/trend-decision.md`.
