# A/B mismo día: superficie MCP vieja vs nueva (10 prompts, 2026-09-16)

Motivación: la comparación anterior (`before.md`/`after.md`, 3 prompts) medía la superficie
vieja y la nueva **en días distintos** contra un corpus de prod que se mueve día a día — el
drift del corpus invalidaba la comparación (distinto ranking, distintos ítems trending). Esta
corrida mide ambos brazos **el mismo día, en la misma ventana de ~22 minutos**, contra el mismo
estado de la API de prod, alternando brazos para repartir cualquier efecto temporal residual.

- **Fecha**: 2026-09-16 (ventana real: 22:44:09 → 23:06:38 CEST, ~22 min para las 20 corridas).
- **`claude --version`**: `2.1.273 (Claude Code)`.
- **Modelo**: `sonnet` (resuelve a `claude-sonnet-5` en el campo `usage`/`modelUsage` de los jsonl).
- **HEAD del repo**: `923f7d5` (rama `main`).

## Diseño de los dos brazos

### Brazo NEW — MCP de prod, streamable-http

Servidor ya desplegado, sin tocar: `https://pguerrero.me/ai-news/mcp`. Config
(`eval-2026-09-16/mcp-new.json`):

```json
{"mcpServers": {"ainews": {"type": "http", "url": "https://pguerrero.me/ai-news/mcp"}}}
```

Verificado antes de correr nada (cliente MCP Python real, `mcp.client.streamable_http`):
`tools/list` → `search`, `get_item`, `find_similar`, `topic_trend`, `get_top` (las 5 tools
nuevas, exactamente como se esperaba).

### Brazo OLD — servidor MCP anterior, reconstruido desde git, ejecutado en local por stdio contra la API de prod

Worktree en el merge-base de la superficie vieja:

```bash
git -C /home/paul/Documentos/proyectos/backend/ai-news-platform worktree add \
  /tmp/claude-1000/-home-paul-Documentos-proyectos-wisdom-paul/619954de-0d73-4c32-9b8c-9b9847d9addf/scratchpad/wt-old \
  300d46a
```

Lanzado con el `.venv` del repo principal (no el worktree, que no tiene su propio venv), vía
un wrapper `.sh` (el `cwd` de un server stdio no es un campo estándar en todas las versiones
de `--mcp-config`, así que se usó el wrapper por seguridad):

`wt-old-mcp.sh` (en el scratchpad de la sesión):
```sh
#!/bin/sh
cd /tmp/.../scratchpad/wt-old || exit 1
export MCP_TRANSPORT=stdio
export MCP_API_BASE_URL=https://pguerrero.me/ai-news
exec /home/paul/Documentos/proyectos/backend/ai-news-platform/.venv/bin/python -m src.mcp.server
```

Config (`eval-2026-09-16/mcp-old.json`):
```json
{"mcpServers": {"ainews": {"command": ".../scratchpad/wt-old-mcp.sh", "args": []}}}
```

Verificado antes de correr nada (mismo cliente MCP Python, `mcp.client.stdio`): `tools/list` →
`search_news`, `semantic_search`, `get_latest`, `get_trending`, `get_briefing` (las 5 tools
viejas). Se probó además una llamada real a `get_trending()`: pidió un guest token contra
`https://pguerrero.me/ai-news/api/auth/guest` (HTTP 200) y devolvió ítems reales de prod
(`Qwen/Qwen3-8B`, `Claude Mythos`, etc.) — confirma que el brazo OLD habla con la API de prod
real, no con un mock.

**Worktree NO borrado** (para auditoría): `/tmp/claude-1000/-home-paul-Documentos-proyectos-wisdom-paul/619954de-0d73-4c32-9b8c-9b9847d9addf/scratchpad/wt-old` (HEAD desacoplado en `300d46a`).

## Comando exacto (idéntico en ambos brazos salvo `--mcp-config`)

Mismo patrón que `before.md`/`after.md`: modelo sonnet, `--strict-mcp-config`,
`--output-format stream-json --verbose`, `--allowedTools mcp__ainews`, `--disallowedTools` con
la lista completa de built-ins, cwd aislado y vacío (sin `CLAUDE.md` ni acceso a la KB).

```bash
EVAL_DIR=docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline/eval-2026-09-16
cd /tmp/task0-isolated-run-eval2026-09-16   # cwd aislado, recreado para esta corrida
claude -p "$(cat $EVAL_DIR/qNN.txt)" --model sonnet --output-format stream-json --verbose \
  --strict-mcp-config --mcp-config $EVAL_DIR/mcp-{new,old}.json \
  --allowedTools mcp__ainews \
  --disallowedTools Read Write Edit NotebookEdit Glob Grep Bash BashOutput KillBash WebFetch WebSearch Task TodoWrite ExitPlanMode SlashCommand ToolSearch Agent \
  > $EVAL_DIR/{new,old}-qNN.jsonl
```

Los 10 prompts (`q01.txt`..`q10.txt`) son copia literal de `.superpowers/sdd/eval-prompts.md`
(q01..q10), extraídos programáticamente (sin retipeo manual) para evitar errores de transcripción.

## Orden real de ejecución (alternado, ver `run-order.log`)

| # | Hora inicio (CEST) | Brazo | Prompt | rc | líneas jsonl |
|---|---|---|---|---|---|
| 1 | 22:44:09 | new | q01 | 0 | 55 |
| 2 | 22:44:09 | old | q01 | 0 | 69 |
| 3 | 22:44:13 | old | q02 | 0 | 49 |
| 4 | 22:45:17 | new | q02 | 0 | 66 |
| 5 | 22:46:37 | new | q03 | 0 | 74 |
| 6 | 22:48:22 | old | q03 | 0 | 76 |
| 7 | 22:50:24 | old | q04 | 0 | 36 |
| 8 | 22:51:22 | new | q04 | 0 | 28 |
| 9 | 22:52:09 | new | q05 | 0 | 58 |
| 10 | 22:53:24 | old | q05 | 0 | 37 |
| 11 | 22:54:26 | old | q06 | 0 | 57 |
| 12 | 22:55:32 | new | q06 | 0 | 78 |
| 13 | 22:57:00 | new | q07 | 0 | 73 |
| 14 | 22:58:24 | old | q07 | 0 | 50 |
| 15 | 22:59:36 | old | q08 | 0 | 44 |
| 16 | 23:00:35 | new | q08 | 0 | 57 |
| 17 | 23:01:35 | new | q09 | 0 | 57 |
| 18 | 23:02:39 | old | q09 | 0 | 74 |
| 19 | 23:04:08 | old | q10 | 0 | 98 |
| 20 | 23:05:46 | new | q10 | 0 | 47 |

20/20 corridas con `rc=0` en el primer intento. **Cero fallos, cero reintentos.** Pausa de
cortesía de ~6s entre llamadas (ritmo humano, sin ráfagas); duración real por llamada
40s–2min. Log completo en `eval-2026-09-16/run-order.log`.

## Verificación de montaje: solo `mcp__ainews__*`, y las tools correctas por brazo

Script de verificación (`extract.py`, scratchpad de la sesión) recorre las 20 corridas y
comprueba que el conjunto de nombres de tool_use por corrida es subconjunto del esperado para
su brazo:

```
=== Tool surface check (unexpected tool names per arm) ===
OK: every run used only tools expected for its arm.

=== Distinct tool names used, by arm ===
new ['mcp__ainews__get_item', 'mcp__ainews__get_top', 'mcp__ainews__search', 'mcp__ainews__topic_trend']
old ['mcp__ainews__get_trending', 'mcp__ainews__search_news', 'mcp__ainews__semantic_search']
```

Ningún jsonl usó tools fuera de `mcp__ainews__*` (el `--disallowedTools` funcionó igual que en
`before.md`/`after.md`). Ninguna corrida OLD usó una tool nueva ni viceversa — el montaje es
correcto. `find_similar` (NEW) y `get_briefing` (OLD) no se usaron en ninguna de las 20
corridas — no es un fallo de montaje, es que el modelo no las necesitó para estos prompts.

## Métricas por corrida

Ver `metrics.tsv` (columnas: `arm`, `prompt`, `tool_calls`, `tool_names`,
`tool_result_chars`, `output_tokens`, `n_links`). `tool_calls` = número total de `tool_use`
del turno; `tool_result_chars` = suma de caracteres de texto de todos los `tool_result`;
`output_tokens` = `usage.output_tokens` del evento `result` final; `n_links` = filas de
`links.tsv` para esa corrida (ver metodología de extracción abajo).

| arm | prompt | tool_calls | tool_names | tool_result_chars | output_tokens | n_links |
|---|---|---|---|---|---|---|
| new | q01 | 10 | get_item×6, search×4 | 25652 | 5024 | 5 |
| new | q02 | 9 | get_item×3, get_top×1, search×5 | 24344 | 6228 | 9 |
| new | q03 | 11 | get_item×5, search×6 | 30019 | 8726 | 13 |
| new | q04 | 3 | search×3 | 8094 | 3487 | 18 |
| new | q05 | 9 | get_item×2, search×7 | 23545 | 5078 | 15 |
| new | q06 | 13 | get_item×6, search×7 | 30007 | 6386 | 11 |
| new | q07 | 17 | get_item×6, get_top×1, search×10 | 34921 | 6174 | 7 |
| new | q08 | 13 | get_item×8, get_top×1, search×4 | 32895 | 4905 | 11 |
| new | q09 | 9 | get_item×3, get_top×1, search×3, topic_trend×2 | 26025 | 4214 | 5 |
| new | q10 | 8 | get_top×1, search×2, topic_trend×5 | 16934 | 4599 | 6 |
| old | q01 | 2 | search_news×1, semantic_search×1 | 4889 | 8519 | 10 |
| old | q02 | 2 | search_news×1, semantic_search×1 | 5174 | 4673 | 9 |
| old | q03 | 2 | search_news×1, semantic_search×1 | 4617 | 9502 | 19 |
| old | q04 | 2 | search_news×1, semantic_search×1 | 4213 | 3829 | 15 |
| old | q05 | **0** | (ninguna) | 0 | 4423 | 5 |
| old | q06 | 8 | search_news×5, semantic_search×3 | 11513 | 4554 | 8 |
| old | q07 | 3 | search_news×2, semantic_search×1 | 5870 | 5110 | 8 |
| old | q08 | 6 | get_trending×1, search_news×4, semantic_search×1 | 15021 | 3859 | 14 |
| old | q09 | 11 | get_trending×1, search_news×9, semantic_search×1 | 30262 | 6448 | 11 |
| old | q10 | **21** | search_news×21 | **219413** | 8674 | 4 |

Nombres de tool acortados sin el prefijo `mcp__ainews__` por espacio; `metrics.tsv` trae el
nombre completo.

### Agregados (media por brazo, 10 corridas c/u)

| arm | tool_calls (media) | tool_result_chars (media) | output_tokens (media) | n_links (media) |
|---|---|---|---|---|
| new | 10.2 | 25 243.6 | 5 482.1 | 10.0 |
| old | 5.7 | 30 097.2 | 5 959.1 | 10.3 |

**Nota sobre el promedio de `tool_result_chars` en OLD**: está inflado por un outlier —
`old q10` (21 llamadas a `search_news`, 219 413 chars). El tool viejo no tiene un `topic_trend`
dedicado, así que para la pregunta de tendencia (q10: comparar "memoria de agentes" vs "prompt
injection" en 6 meses) el modelo hizo fuerza bruta: 3 queries × 6 buckets mensuales (`date_from`/
`date_to`, `limit=100`) + 3 queries de barrido inicial = 21 llamadas. Sin ese outlier, la media
de `tool_result_chars` de OLD cae a ~9 480 (por debajo de NEW). Este es exactamente el patrón
que motivó el diseño de `topic_trend` en la superficie nueva: NEW resolvió la misma pregunta
(q10) con 8 llamadas (`topic_trend`×5, `search`×2, `get_top`×1) y 16 934 chars.

**Nota sobre `old q05`**: la corrida terminó con `rc=0` pero **0 tool calls** — el modelo
respondió íntegramente "de memoria entrenada", declarándolo explícitamente en la respuesta
("no tengo acceso a WebSearch/WebFetch en esta sesión... esto sale de memoria entrenada, no de
verificación en vivo"). No es un fallo técnico (el proceso terminó limpio, sin reintento), es
una elección del modelo de no invocar el MCP para ese prompt en ese brazo — se registra tal
cual, sin retirarlo del dataset.

## Tools usadas por brazo (todas las corridas)

- **NEW**: `search`, `get_item`, `get_top`, `topic_trend`. No se usó `find_similar`.
- **OLD**: `search_news`, `semantic_search`, `get_trending`. No se usó `get_briefing`.

## Metodología de extracción de `links.tsv` (heurística, léase con cautela)

`links.tsv` se genera con un extractor por regex (`extract.py`, scratchpad de la sesión) sobre
el texto de la respuesta final (`result` del evento `type=="result"`), NO sobre los
`tool_result` crudos. Reglas:

1. Detecta enlaces markdown `[texto](url)`, URLs `http(s)://` sueltas, citas sin esquema en
   dominios conocidos (`arxiv.org/...`, `github.com/...`, `simonwillison.net/...`, lista de
   TLDs restringida para evitar falsos positivos con nombres de fichero tipo `SKILL.md`), e
   ids sueltos `arXiv:2603.12277` (sin URL) normalizados a `https://arxiv.org/abs/...`.
2. Trata como "ítem citable" cualquier línea de lista numerada (`1. **Título**...`) o con
   viñeta (`- **Título**...` / `` - `código` ``), y cualquier párrafo sin viñeta que arranque
   con negrita **y** contenga al menos una cita (para no capturar frases en negrita usadas
   solo como énfasis, p. ej. "**No, no hay señal agregada de subida**").
3. Si el ítem no trae ninguna URL, se registra igual con `url` vacía (mención sin enlace) —
   así se preservan casos como los nombres de proyecto en las respuestas de tendencia
   (q09/q10), que citan `ospec`, `sample-specship`, etc. sin link literal.
4. Deduplica por URL dentro de la misma respuesta (una URL citada dos veces en el mismo texto
   cuenta una vez).

**Esto es best-effort, no un parser semántico.** Se verificó manualmente contra ~7 de las 20
respuestas (q01, q03, q04, q09, q10 en ambos brazos donde aplica) y coincide con una lectura
humana de "qué cita esta respuesta", pero puede: (a) perder alguna mención inline suelta en
medio de un párrafo de prosa sin viñeta ni negrita, y (b) capturar como "mención" alguna frase
de comentario/conclusión en negrita dentro de una lista con viñetas que no es estrictamente una
cita (ej. bullets de "Lectura de los números" en las respuestas de tendencia). El
`blind-labeler` que etiquete relevancia debe tratar `links.tsv` como punto de partida, no como
verdad absoluta, y puede volver a leer el `result` completo de cada jsonl si una fila le
resulta ambigua.

## Fallos

Ninguno. Las 20 corridas terminaron con `rc=0` en el primer intento (0 reintentos disparados).

## Sin conclusiones de relevancia

Este documento reporta métricas de proceso (tool calls, volumen de tool_result, tokens de
salida, enlaces citados) y verificación de montaje. Deliberadamente **no** incluye ningún
juicio sobre si los enlaces citados por NEW u OLD son más relevantes — eso corresponde al
etiquetado ciego posterior, ya en marcha con el agente `blind-labeler`.
