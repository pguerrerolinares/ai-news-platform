# A/B superficie MCP vieja vs nueva — mismo día, mismo corpus (2026-09-16)

Repite la medición del criterio §8.1 corrigiendo el defecto de la primera: allí se comparó "antes" (15-sep, superficie vieja) contra "después" (16-sep, nueva) con **un día de drift del corpus** de por medio. Aquí los dos brazos corren el **mismo día contra el mismo corpus de prod**.

## Método

- **Brazo OLD**: server MCP del merge-base `300d46a` reconstruido en un worktree y ejecutado por **stdio en local contra la API de prod** (`MCP_API_BASE_URL=https://pguerrero.me/ai-news`). `tools/list` verificado: `search_news, semantic_search, get_latest, get_trending, get_briefing`.
- **Brazo NEW**: MCP de prod (`https://pguerrero.me/ai-news/mcp`), streamable-http. `tools/list`: `search, get_item, find_similar, topic_trend, get_top`.
- **10 prompts** (`.superpowers/sdd/eval-prompts.md`): 8 de descubrimiento por problema, 2 de tendencia. 20 corridas, orden alternado entre brazos, 0 fallos.
- Misma receta en ambos: `claude -p --model sonnet --output-format stream-json --verbose --strict-mcp-config --mcp-config <arm> --allowedTools mcp__ainews --disallowedTools <todas las built-in>`, cwd aislado y vacío. Verificado que en cada jsonl solo hay `tool_use` de `mcp__ainews__*` y que los nombres corresponden al brazo.
- Ficheros: `{old,new}-qNN.jsonl` (20 corridas crudas), `metrics.tsv` (métricas de proceso por corrida), `links-all-mentions.tsv` (todas las menciones detectadas, extracción laxa: 203 filas con duplicados entre secciones de una misma respuesta), `links-blind.tsv`/`links-labeled.tsv`/`links-key.tsv` (la **muestra realmente etiquetada**: 93 enlaces únicos por respuesta, extracción con dedupe, barajados; la clave del brazo se unió después de etiquetar) y `run-order.log`.
- Nota: los recuentos de esta página salen de la extracción con dedupe (49 OLD / 45 NEW). `links-all-mentions.tsv` cuenta cada aparición y por eso da más filas; se conserva por transparencia, no es la base del etiquetado.

## Métricas de proceso (10 corridas por brazo)

| | OLD | NEW |
|---|---|---|
| Tool calls | 57 | **102** |
| Chars de `tool_result` | 309.257 | **274.237** |
| `output_tokens` | 59.591 | **54.821** |
| Enlaces (URL) citados | 49 | 45 |
| IDs de arXiv únicos citados | 35 | 32 |

El brazo nuevo hace ~1,8× llamadas pero consume **12% menos contexto de tool_result** y **8% menos tokens de salida**: llamadas más pequeñas y dirigidas (`search` acotado + `get_item` para verificar el abstract) en vez de listados grandes. Tools usadas: OLD `search_news` (9 corridas), `semantic_search` (8), `get_trending` (2); NEW `search` (10), `get_item` (8), `get_top` (5), `topic_trend` (2). **`find_similar` no se usó en ninguna corrida** — cuarta tanda consecutiva sin usarse.

## Relevancia de los enlaces (etiquetado ciego)

93 enlaces de ambos brazos, barajados, etiquetados R/N por un agente que solo vio `links-blind.tsv` + los prompts (sin saber el brazo), con 10 URLs abiertas para verificar.

| Brazo | q01 | q02 | q03 | q04 | q05 | q06 | q07 | q08 | q09 | q10 | TOTAL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD | 7/8 | 3/3 | 3/4 | 10/10 | 0/0 | 4/4 | 7/7 | 13/13 | 0/0 | 0/0 | **47/49 (96%)** |
| NEW | 5/5 | 1/1 | 0/0 | 8/8 | 8/12 | 4/4 | 7/7 | 7/8 | 0/0 | 0/0 | **40/45 (89%)** |

**Este número NO se puede leer como "la superficie vieja es más precisa".** Tres razones, todas verificadas en los jsonl:

1. **La cobertura no es comparable.** En q05 (orquestación multiagente) el brazo OLD hizo **0 tool calls** y respondió de memoria entrenada: *"No tengo acceso a WebSearch/WebFetch en esta sesión … esto sale de memoria entrenada, no de verificación en vivo"*. Cero enlaces y cero riesgo de fallar el etiquetado. El brazo NEW hizo 9 llamadas y citó 12, de los que 8 son relevantes. Premiar al que no contesta es un artefacto de la métrica.
2. **El extractor de enlaces penaliza al brazo nuevo.** Solo cuenta URLs con dominio; las citas en formato `arXiv:2602.14878` no entran. OLD cita 35 ids de arXiv (23 como URL) y NEW 32 (18 como URL). En q03 el brazo NEW dio 0 URLs pero sí citó papers por id, así que su fila `0/0` no significa "no encontró nada".
3. **Muestra pequeña**: 49 vs 45 enlaces. Dos o tres enlaces mueven el porcentaje ~5 puntos.

**Conclusión honesta sobre precisión: no hay evidencia de que la superficie nueva mejore ni empeore la relevancia de las citas.** Los dos brazos aciertan casi siempre en lo que citan.

## Tendencias (q09, q10): aquí sí hay diferencia, y es cualitativa

Ninguno cita enlaces, así que el etiquetado no los cubre. Leídas las 4 respuestas:

- **q09 ("¿sube spec-driven development?")**: OLD hace ventanas con `search_news` y concluye *"Sí, hay señal de subida"* con conteos crudos (5, 3, 2 por periodo). NEW usa `topic_trend` y concluye *"No, es ruido, no tendencia"*, explicando que el corpus pasa de ~80 a ~800+ items/semana y que el `share` nunca supera el 0,6%. **Las conclusiones son opuestas y la del brazo nuevo es la defendible**: contar hits sin normalizar por el crecimiento del corpus fabrica tendencias que no existen.
- **q10 (memoria vs prompt injection)**: OLD construye la tabla con `search_news` y **choca con el techo de resultados** (*"100 (techo, ≥100)"*), es decir, mide con una regla truncada; NEW da `n` y `share` por mes y marca septiembre como parcial (254 items a día 16).

Esto es exactamente lo que `topic_trend` venía a resolver, y no aparece en ninguna métrica agregada.

## Qué queda en pie

- **Ganancia demostrada**: preguntas de tendencia bien respondidas (normalizadas, sin techos) — capacidad que antes no existía; y ~12% menos contexto consumido por respuesta pese a hacer más llamadas.
- **Sin evidencia de ganancia**: precisión de las citas en preguntas de descubrimiento.
- **Riesgo detectado en la superficie vieja** (ya retirada): responder de memoria entrenada sin tocar el corpus cuando la pregunta no encaja con las tools disponibles (q05).
- **`find_similar` sigue sin usarse por el agente** en 4 tandas (14 corridas con la superficie nueva). O su descripción no invita a usarla, o el patrón "dame similares a este item" no aparece en este tipo de preguntas. Candidata a revisar o retirar.

## Limitaciones

Un solo etiquetador LLM juzgando por título/URL (10 verificadas abriendo la página); 10 prompts escritos por el orquestador, no muestreados de uso real; una corrida por celda (sin repeticiones, así que la varianza del modelo no está medida); el brazo OLD corre por stdio en local y el NEW por HTTP en prod (mismo backend, distinto transporte); `n_links` depende de un regex imperfecto (ver punto 2 arriba).
