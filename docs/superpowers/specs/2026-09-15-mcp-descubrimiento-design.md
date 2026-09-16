# Spec — MCP de ai-news: superficie de descubrimiento (B1)

- Fecha: 2026-09-15 · Estado: pendiente de review de Paul (auditada: "aprobable con cambios", cambios integrados)
- Track B: superficie pública nueva + endpoint nuevo + label de Traefik; sin cambio de schema BD.
- Código afectado: `src/mcp/server.py`, `src/mcp/client.py`, `src/rag/retriever.py`, `src/api/routes/search.py`, `src/api/routes/items.py`, `src/api/routes/stats.py`, `src/api/schemas.py`, `src/api/app.py` (log), `docker-compose.coolify.yml` (label Traefik), tests.

## 1. Propósito y consumidor

- **Consumidor principal**: los agentes de Paul (Claude Code). El MCP es público "de rebote" (ADR-001): defensa mínima, no es un producto.
- **Caso de uso central**: sesiones de brainstorming/mejora de proyectos buscando qué ha hecho la comunidad o qué dicen los papers sobre un problema ("descubrimiento por problema"), más **tendencias en el tiempo** de un tema. NO es catch-up diario.

## 2. Problemas del estado actual (verificados)

1. Tools `def` sync + `httpx.Client` sync: `mcp` 1.30 las ejecuta con `fn(**args)` en el event loop (`mcp/server/fastmcp/utilities/func_metadata.py:115`) → una llamada lenta bloquea el server para todos. Medido: 2 llamadas concurrentes con backend de 1s → 2.02s sync vs 1.01s async.
2. `get_trending` usa `/api/items?trending=true` (sin ventana, orden por fecha) en vez de `/api/items/trending` → devolvió un artículo del 2026-06-19 como trending en septiembre.
3. Todo el tráfico MCP entra a la API con un guest token desde la IP del contenedor → un bucket de rate-limit compartido (30/min; 20/min en similar/semantic).
4. **Borde Traefik también global**: la label `mcp-ratelimit.sourcecriterion.ipstrategy.depth=1` (`docker-compose.coolify.yml:158`) con clientes que llegan sin XFF (no hay CDN delante: `pguerrero.me` resuelve directo a Hetzner) produce source vacío → 3 req/s + burst 10 para todos los clientes MCP juntos.
5. El output descarta `published_at`.
6. "pts" mezcla descargas HF, puntos HN, stars y 0 de arxiv/RSS/webscraper; `composite_score` (0-1) no se expone.
7. Topic inválido → `"No items found."` silencioso; el schema es `str` libre.
8. Sin `id`, fetch por id ni similares, aunque existen `/api/items/{id}` y `/{id}/similar`.
9. `get_briefing` expone métricas internas del pipeline, solo top 5.
10. `semantic_search` sin filtros y con sesgo de recencia oculto: el retriever busca 30 días y cae al rango completo si `< limit` (`src/rag/retriever.py:18,57-70`).
11. HNSW devuelve como máximo `hnsw.ef_search` (40 por defecto) filas: con filtros WHERE restrictivos o LIMIT > 40 devuelve menos resultados sin error (probe en pgvector 0.8.1: `LIMIT 1000 → 40`; `WHERE 10% LIMIT 50 → 5`).

## 3. Evidencia usada

- Search→fetch por id: Sieve (arXiv 2608.02751; Wang, Chen, Yin; 2026): más accuracy con 20.7-50.6% menos tokens. 8/12 MCP servers comparables separan search de fetch.
- Descripciones: "MCP Tool Descriptions Are Smelly!" (arXiv 2602.14878; Hasan, Li, Rajbahadur; 2026): 97.1% de 856 tools con smell; propósito+límites+parámetros por intención → +5.85pp éxito mediano.
- Nº de tools: RAG-MCP (arXiv 2505.03275; Gan, Sun; 2025) mide degradación con catálogos grandes; con 5 tools no aplica.
- Fusionar búsquedas, enums, texto vs JSON: sin evidencia específica → criterio.
- Prior art: 0/12 servers exponen similares ni tendencias por tema; los comparables directos (treesoop/ai-news-mcp, JoonJ14/ai-newsroom) son de catch-up.
- Spec MCP 2026-07-28 (stateless); SDK `mcp` v2.0.0 renombra `FastMCP`→`MCPServer` (rompe import) → pin `<2`. Prod MCP corre 1.30.0.
- Tendencia semántica (decisión §6 (a), delegada en consultor): Steck, Ekanadham, Kallus, "Is Cosine-Similarity of Embeddings Really About Similarity?", WWW'24 Companion, arXiv:2403.05440 (la distancia coseno absoluta no es comparable entre queries — motiva no calibrar un τ global); Arampatzis, Kamps, Robertson, "Where to stop reading a ranked list?", SIGIR'09 (el cutoff óptimo de un ranking es específico de la query, no una constante).

## 4. Diseño

### 4.1 Arquitectura
- Se mantiene: MCP = cliente de su propia REST API (`http://api:8000`), no toca BD.
- Tools `async` + `httpx.AsyncClient`; salida `structuredContent` vía modelos pydantic (el SDK añade bloque de texto); errores como `ToolError`.
- `mcp>=1.29,<2`; `stateless_http=True` (verificado compatible).
- `ToolAnnotations(readOnlyHint=True, openWorldHint=False)` — **camelCase**: en snake_case (`read_only_hint`) el modelo lo acepta como extra y queda en `None` sin error.
- **Reenvío de `X-Forwarded-For`**: la tool lee `ctx.request_context.request.headers` (verificado en 1.30 con `stateless_http=True`; en stdio `request` es `None` → guard: sin cabecera, no se reenvía) y la reenvía a la API. `get_client_ip` (`src/api/ratelimit.py:27`) confía en proxies privados/docker y toma la IP no privada más a la derecha. Anti-spoofing: Traefik borra `X-Forwarded-*` de orígenes no confiables y el proxy añade la IP real.
- **Borde Traefik**: se elimina la label `ipstrategy.depth=1` → `sourceCriterion` por `RemoteAddr` (correcto sin CDN). Cada cliente MCP tiene su bucket de 3 req/s.
- **Observabilidad**: `metrics_middleware` (`src/api/app.py:208-225`) añade `client_ip=get_client_ip(request)` al log estructurado de cada request.

### 4.2 Superficie (5 tools; se eliminan get_latest, get_trending, get_briefing, semantic_search)

Item compacto en listados: `id · title · source · topic · published_at (YYYY-MM-DD) · composite_score (0-1) · summary · url`.

| Tool | Contrato | API |
|---|---|---|
| `search(query, mode=semantic\|keyword, topic?, source?, date_from?, date_to?, limit≤50)` | items por relevancia | keyword: `/api/search` **+ filtro `source`**. semantic: `/api/search/semantic` **+ filtros, sin sesgo de recencia** |
| `get_item(id)` | item completo + `full_text` **entero, sin tope** + `discussion_url` (de `metadata.hn_url`; null si no hay) + `engagement` + `author` | `/api/items/{id}` con schema de detalle |
| `find_similar(id, limit≤20)` | vecinos semánticos | `/api/items/{id}/similar` (existe) |
| `topic_trend(query, method=keyword\|semantic, granularity=week\|month, since, max_distance?)` | ver §4.3.5 | endpoint nuevo `/api/stats/trend` |
| `get_top(days=7, topic?, source?, limit≤50)` | ranking `composite_score` en ventana | `/api/items/top` (existe) |

- Enums `Literal`: `topic ∈ {models, tools, papers, products, open_source, agents, regulation}`; `source ∈ {github, arxiv, rss, hackernews, huggingface, github_search, webscraper}` (coincide con `/api/sources` en prod).
- `engagement: {kind, value} | null`, con `kind ∈ {points, stars, downloads, upvotes}`:
  - hackernews → `points`; github, github_search → `stars`;
  - huggingface → `downloads` si `metadata.type == "model"`, `upvotes` si `"daily_paper"`;
  - arxiv, rss, webscraper (score 0) → `null`.
- Fechas `YYYY-MM-DD`. Argumento inválido / id inexistente → `ToolError` accionable; lista vacía solo si no hay resultados reales.
- Descripciones con propósito, límites y parámetros por intención (Smelly). `topic_trend` documenta que la fecha efectiva de repos/modelos es la de primera captura (ver §4.3.4).

### 4.3 Cambios en la API

1. **Scan exacto SIEMPRE en la búsqueda semántica y en `trend` semántico** (no solo con filtros: `limit` llega a 50 > `ef_search`=40). `SET LOCAL enable_indexscan = off` en la transacción de la consulta. HNSW no sirve: devuelve ≤ `hnsw.ef_search` filas. Coste: 17k×512 dims ≈ decenas de ms; crece lineal con el corpus (~30k items/año), aceptable durante años. `find_similar` sin filtros y `limit≤20` sigue con HNSW.
2. **`/api/search` + filtro `source`** (hoy solo `topic`, `date_from`, `date_to`: `search.py:61-87,96-105`).
3. **`/api/search/semantic` + filtros** `topic, source, date_from, date_to`; parámetro `recent_first` (default `true`, porque la web lo usa: `Discover.tsx:138`); el MCP envía `recent_first=false` (el filtro temporal es explícito vía `date_from`). Fallo del embedding → 503 `EMBEDDING_UNAVAILABLE` (nunca `[]`); `q` ≤ 200 chars; `date_from > date_to` → 422 (ver §4.6).
4. **`NewsItemDetail`** en `/api/items/{id}`: añade `full_text`, `discussion_url`, `engagement` (reglas §4.2).
5. **`/api/stats/trend?q&method&granularity&since&max_distance`** (rate-limit 20/min, `since ≤ 24 meses`):
   - Bucket: `date_trunc(unit, coalesce(published_at, created_at), 'UTC')`; semanas ISO (lunes). Buckets vacíos rellenados (count 0; en Python sobre la serie de buckets esperada).
   - `keyword`: match FTS sobre `search_vector`, `GROUP BY bucket, source`. `max_distance` se ignora.
   - `semantic`: 1 embedding de la query (`text-embedding-3-small`, ~$3e-7/llamada) + scan exacto de distancias (`SET LOCAL enable_indexscan = off`). **Sin τ ni calibración** (pre-check §6 (a) STOP: un corte único no separa relevantes de no relevantes entre queries — ver decisión). El cutoff es un parámetro explícito **`max_distance: float = 0.40`** (`ge=0.20, le=0.60`; 422 fuera de rango) y la respuesta añade, por bucket, el conteo acumulado a 5 distancias fijas: constante `TREND_DISTANCE_EDGES = (0.30, 0.35, 0.40, 0.45, 0.50)` en `src/api/trend.py`. Una sola query agrupada por `bucket, source, width_bucket(dist, ARRAY[0.30,0.35,0.40,0.45,0.50]), (dist < :max_distance)`, con `dist < greatest(:max_distance, 0.50)` en el `WHERE` (JOIN con embedding del modelo activo); de esas filas se derivan tanto `count`/`by_source` (a `max_distance`) como `by_distance` (acumulado por banda). `total_in_bucket` cuenta solo items **con embedding del modelo activo** (JOIN), para que `share` no mezcle cobertura de embeddings.
   - Respuesta: `{query, method, granularity, since, max_distance: float|None, distance_edges: list[float]|None, buckets: [{bucket, count, total_in_bucket, share, by_source, by_distance: dict[str,int]|None}]}`. `max_distance`, `distance_edges` y `by_distance` son `null` en `keyword`; `by_distance` trae siempre las 5 claves `"0.30".."0.50"` (0 si vacío) en `semantic`.
   - Fecha efectiva: `published_at` es `pushed_at` en github_search, `now()` de captura en github trending y `lastModified` en HF, y el upsert no la actualiza (`store.py:85-105`) → para repos/modelos significa "primera captura". Se documenta en la descripción de la tool.
   - El consumidor es un LLM: `topic_trend` (Task 7) documenta que la banda correcta depende del tema — leer la forma en la banda más ajustada con ≥20 items totales; si hasta 0.50 está casi vacío, el corpus no tiene señal para esa query (usar `method=keyword`).

### 4.4 Errores (cliente MCP)
Mapeo por `error.code` del cuerpo (`{"error": {"code", "message"}}`), no solo por status:
- `NOT_FOUND` → "item not found"; `EMBEDDING_NOT_FOUND` → "item exists but has no embedding yet; similar unavailable";
- `EMBEDDING_UNAVAILABLE` (503) → "semantic search unavailable (embedding provider down); try mode=keyword" (más accionable que el genérico 5xx; enmienda 4.6);
- 422 → detalle de validación; 429 → "rate limited, retry in Xs"; timeout/5xx → "backend unavailable".
- Se mantiene refresh del guest token en 401. Nota: el SDK antepone `"Error executing tool <name>: "` al mensaje.

### 4.6 Enmienda 2026-09-16 (review whole-branch de la rama `feat/mcp-descubrimiento`)

Completa la promesa de §4.2 ("argumento inválido / id inexistente → error accionable; lista vacía
solo si no hay resultados reales"), que el código no cumplía todavía en tres puntos:

1. **Fallo del embedding en `/api/search/semantic`**: `Retriever.retrieve` capturaba la excepción
   del proveedor y devolvía `[]` (200 silencioso) — decisión de Paul: propagar
   (`EmbeddingUnavailableError`) y que la ruta responda **503 `EMBEDDING_UNAVAILABLE`**, igual que
   ya hacía `/api/stats/trend`. Aplica a todo caller, incluida la web (`Discover.tsx`), sin
   condicionar a `recent_first`. `src/rag/chat.py` (el otro consumidor de `Retriever`) también fue
   silencioso (RAG respondía sin contexto real, sin avisar); ahora emite un evento SSE
   `error {code: EMBEDDING_UNAVAILABLE}` + `done` y no llama al LLM — mismo principio de fallo
   ruidoso, canal propio porque es streaming.
2. **`GET /api/items/{id}/similar` con id inexistente** devolvía `EMBEDDING_NOT_FOUND` sin comprobar
   si el item existía → el cliente MCP mentía ("item exists but has no embedding yet"). Ahora
   comprueba existencia del item cuando no hay embedding: **404 `NOT_FOUND`** si no existe, 404
   `EMBEDDING_NOT_FOUND` solo si existe de verdad.
3. **`date_from > date_to`** en `search` (MCP y API) devolvía lista vacía; ahora 422/`ValueError`
   accionable (menciona ambos parámetros) antes de llamar a la API. `get_top`/`topic_trend` no
   aceptan rango de fechas, no aplica.
4. **`q` sin tope** en `/api/search`, `/api/search/semantic` y la tool `search`: se añade
   `max_length=200` (mismo límite que `/api/stats/trend`), para que un texto larguísimo dé un 422
   de validación en vez de alcanzar al proveedor de embeddings.

### 4.5 Seguridad
- IPI: instrucciones del server y descripciones declaran `title/summary/full_text` como contenido de terceros no confiable (dato, no instrucción); structuredContent los mantiene en campos separados. Sin sanitización.
- Enums cerrados, límites en la API, rate-limit por cliente real en borde y API.

## 5. Testing
- **Unit MCP** (API mockeada): contrato de salida de las 5 tools; mapeo por `error.code` → ToolError (esperando el prefijo del SDK); enum inválido; XFF reenviado y guard stdio.
- **Unit concurrencia**: backend mock con `sleep 0.3s`, dos llamadas concurrentes, `assert elapsed < 1.5 × 0.3s`.
- **Contrato `tools/list`**: aserción por proyección (nombres, `enum` de `topic/source/mode/method/granularity`, `required`, `annotations == {"readOnlyHint": true, "openWorldHint": false}`), no snapshot completo (el `outputSchema` arrastra `title`s de pydantic que cambian con versiones).
- **Integración API** (Postgres + pgvector de `tests/integration/conftest.py`):
  - semantic con filtro: con tablas pequeñas el planner no elige HNSW y el test pasaría sin el fix (medido con 200 y 1000 filas) → el test fuerza el camino de índice con `SET LOCAL enable_sort = off`; ≤10% cumplen el filtro, `limit=10` → `len == 10` (medido: sin fix 3/10, con fix 10/10).
  - trend keyword/semantic: buckets vacíos presentes, UTC, `share` con `total_in_bucket` solo con embedding; `build_buckets` recibe además las bandas (`bands: dict[tuple[date,str,int], int]`) y produce `by_distance` acumulado con `"0.30"…"0.50"` siempre presentes (0 si vacío) y `None` en keyword; integración semantic con 3 vectores a distancia 0.10/0.38/0.47 de la query → `by_distance == {"0.30":1,"0.35":1,"0.40":2,"0.45":2,"0.50":3}`, `count == 2` con `max_distance` default (0.40), y `count == 3` con `max_distance=0.5`; `max_distance=0.7` → 422; en keyword, `max_distance`/`distance_edges`/`by_distance` son `None`.
  - detalle: `engagement.kind` por fuente y tipo HF; `discussion_url`.
- **Smoke prod post-deploy**: 5 tools contra `https://pguerrero.me/ai-news/mcp`; el log de la API muestra `client_ip` público, no la IP del contenedor MCP.
- **Manual (no CI)**: 3-4 prompts de research reales en Claude Code, observar selección de tools.

## 6. Pre-checks (antes de código; si alguno refuta un supuesto, se reabre esa decisión con Paul)
- (a) **Calibración de τ y validez de un τ global** — **ejecutado → STOP** (spread 0.19 > 0.10 entre el mejor τ por query de 5 queries de research reales etiquetadas: `docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline/tau.md`). Un τ único no separa relevantes/no relevantes entre queries; top-K fijo tampoco (dilución con K grande, ver `tau_analysis.py` en el mismo directorio). Paul delegó la decisión en un consultor: se elimina la calibración y el cutoff pasa a ser el parámetro explícito `max_distance` con bandas de distancia devueltas al consumidor (§4.3.5, `docs/superpowers/sdd/trend-decision.md`).
- (b) `full_text`: max/p99 de longitud por fuente en prod (read-only). Informativo: Claude Code guarda a fichero las respuestas >25k tokens, no trunca.
- (c) Cobertura de embeddings en prod (items sin embedding del modelo activo) y presencia de `metadata.type` en items HF históricos.
- (d) Traefik de Coolify: config de `forwardedHeaders` (`trustedIPs`/`insecure`) y confirmar que sin `depth=1` el `sourceCriterion` usa la IP real.
- (e) Resuelto al planificar: la web usa `/api/search/semantic` (`Discover.tsx:138`) → `recent_first` es parámetro con default `true`.

## 7. Rollout
- API (aditiva) + MCP + label Traefik en el mismo deploy Coolify; nombres de tools cambian sin aliases. Rollback: `git revert` del merge.
- Healthcheck del contenedor MCP (`/health`, ADR-004) no cambia.

## 8. Criterios de éxito
1. **Baseline vs después**: 3 prompts de research reales ejecutados ANTES de tocar nada y DESPUÉS del deploy, registrando tool calls, tokens de output y si llegó a papers/repos relevantes (prompts y transcripts guardados en `docs/superpowers/specs/` junto a esta spec para reproducibilidad).
2. Test de concurrencia, contrato `tools/list` e integración semantic-con-filtro en verde.
3. Ninguna tool devuelve lista vacía ante argumento inválido.
4. Log de la API con `client_ip` público de cliente tras una llamada MCP en prod.

## 9. Documentación
ADR-006 (superficie MCP de descubrimiento, con evidencia y la decisión de tendencia semántica por bandas de distancia — sin τ global, ver §4.3.5); enmienda ADR-002 (dice rate-limit guest "por jti"; el código usa `get_client_ip`); enmienda ADR-001 (borde Traefik por `RemoteAddr`); `AGENTS.md` (tabla API, trend, detalle, filtros); README sección MCP. KB: nota `ai-news-pipeline` vía /document.

## 10. Fuera de alcance
B2 residual (MemoryStorage por worker, emisor de tokens para `/api/chat`); calidad de summaries del clasificador; migración a SDK v2; `also_covered_by` (el dedup no guarda clusters); tools de catch-up; resources/prompts/MCP Registry; eval automatizado de selección de tools.
