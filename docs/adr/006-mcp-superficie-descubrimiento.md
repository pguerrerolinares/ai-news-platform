# ADR-006: Superficie MCP de descubrimiento

**Date**: 2026-09-15
**Status**: Accepted
**Track**: B (superficie pública nueva + endpoint nuevo + label de Traefik; sin cambio de schema)

## Context

El MCP (ADR-001) exponía 5 tools de catch-up (`search_news`, `semantic_search`, `get_latest`,
`get_trending`, `get_briefing`) que devolvían texto. Su consumidor real son los agentes de Paul en
sesiones de brainstorming: "¿qué ha hecho la comunidad / qué dicen los papers sobre X?" y "¿sube X?".
Problemas verificados: tools sync que bloqueaban el event loop (2 llamadas concurrentes: 2.02s vs
1.01s async); `get_trending` sin ventana temporal; sin fechas ni ids en la salida; "pts" no
comparables entre fuentes; topic inválido devolvía "No items found." en silencio; un solo bucket de
rate-limit para todos los clientes MCP (en la API y en Traefik); HNSW devolvía como máximo
`hnsw.ef_search` (40) filas con filtros o `limit > 40`.

## Decision

- 5 tools con propósito único, salida estructurada (pydantic → `structuredContent`), `async`,
  `ToolAnnotations(readOnlyHint=True, openWorldHint=False)`: `search(mode=semantic|keyword)`,
  `get_item`, `find_similar`, `topic_trend`, `get_top`. Sin aliases de las antiguas.
- Enums cerrados (`Literal`) para `topic`/`source`; errores accionables en vez de listas vacías.
- `get_item` devuelve `full_text` entero (sin tope: un tope traslada coste al agente) y
  `engagement {kind: points|stars|downloads|upvotes, value} | null`.
- API: filtros en la búsqueda semántica con **scan exacto** (`SET LOCAL enable_indexscan = off`);
  `/api/stats/trend` (keyword = FTS; semantic = sin τ global — pre-check (a) lo refutó, spread 0.19 —
  cutoff explícito `max_distance` (default 0.40) + `by_distance` acumulado a 5 bandas fijas
  `TREND_DISTANCE_EDGES`, decisión delegada en consultor, ver
  `docs/superpowers/specs/2026-09-15-mcp-descubrimiento-baseline/tau.md`).
  En `trend` semántico el mismo guard (`force_exact_scan`) se llama antes de la query agrupada, pero
  es un **no-op estructural** ahí, no una fuerza de plan: el access method HNSW de pgvector solo
  implementa orden por `<->`/`<=>` (`amcanorderbyop`), no un filtro `WHERE distance < x` indexable
  (`amsearcharray`/predicado); el planner nunca considera HNSW para esta forma de query — `GROUP BY`
  sin `ORDER BY ... LIMIT` — con o sin el guard. Verificado con `EXPLAIN (ANALYZE, BUFFERS)` contra
  220 filas sembradas (60 cercanas, 160 lejanas): mismo plan (`Seq Scan` + `Filter` post-scan,
  `Rows Removed by Filter: 160`) con el guard activo y con él desactivado forzando
  `enable_seqscan=off; enable_bitmapscan=off`. Confirmado en el catálogo: `pg_amop` para `hnsw`/`vector_cosine_ops` solo registra un operador de ordenación (`amoppurpose = 'o'`), nunca de filtro. Se deja como guardia defensiva
  para si la query cambia algún día a `ORDER BY distance LIMIT` (ahí sí sería necesaria), no porque
  cambie el plan hoy.
- El MCP reenvía el `X-Forwarded-For` del cliente; la API loggea `client_ip`; Traefik limita por
  `RemoteAddr` (enmienda ADR-001). `stateless_http=True`. `mcp~=1.29` (el SDK 2.x renombra
  `FastMCP` → `MCPServer`).

## Evidence

- Buscar → traer por id: Sieve (arXiv 2608.02751; Wang, Chen, Yin; 2026): más accuracy con
  20.7-50.6% menos tokens que traer la página completa; 8/12 MCP servers comparables separan search
  de fetch.
- Descripciones: "MCP Tool Descriptions Are Smelly!" (arXiv 2602.14878; Hasan, Li, Rajbahadur; 2026):
  97.1% de 856 tools con smells; propósito + límites + parámetros por intención → +5.85pp de éxito
  mediano.
- Nº de tools: RAG-MCP (arXiv 2505.03275; Gan, Sun; 2025) mide degradación con catálogos grandes; 5
  tools no aplica.
- Tendencia semántica sin τ global: Steck, Ekanadham, Kallus, "Is Cosine-Similarity of Embeddings
  Really About Similarity?", WWW'24 Companion, arXiv:2403.05440 (la distancia coseno absoluta no es
  comparable entre queries — motiva no calibrar un cutoff único); Arampatzis, Kamps, Robertson,
  "Where to stop reading a ranked list?", SIGIR'09 (el punto óptimo de corte de un ranking es
  específico de la query, no una constante). Confirmado empíricamente en local: pre-check (a),
  spread=0.19 entre el mejor τ por query (ver `tau.md`).
- Fusionar búsquedas, enums y texto vs JSON: sin evidencia específica → criterio propio.
- Prior art: ningún MCP comparable (0/12) expone similares ni tendencias por tema.

## Alternatives considered

- **Aditivo** (mantener las 5 antiguas + 3 nuevas): sin rotura, pero latest/trending/briefing/top
  solapan propósito (el smell "Unclear Purpose").
- **Contrato mínimo** search/fetch/trend: pierde el ranking por ventana (`composite_score`).
- **Umbral τ global calibrado en prod**: descartado — pre-check (a) lo refutó (spread 0.19 > 0.10
  entre el mejor τ por query); un corte único no separa relevantes de no relevantes entre queries.
  **Top-K por fecha**: también descartado (dilución con K grande, mismo pre-check). Se eligió un
  cutoff explícito (`max_distance`) más un histograma acumulado por bandas fijas (`by_distance`),
  que traslada la lectura de la forma de la distribución al consumidor (un LLM) en vez de que el
  servidor calibre un corte.
- **HNSW con `ef_search`/`iterative_scan`**: escala mejor, pero depende de la versión de pgvector y
  da recall aproximado; a ~17k items el scan exacto cuesta decenas de ms.

## Consequences

- Los nombres de tools cambian: clientes existentes ven la lista nueva al abrir sesión.
- El scan exacto crece lineal con el corpus (~30k items/año); revisar si pasa de ~200k.
- `find_similar` falla con error claro para items aún sin embedding — y solo para esos: si el item
  no existe, es `NOT_FOUND` (404), no `EMBEDDING_NOT_FOUND` (enmienda 2026-09-16, ver abajo).
- Rollback: `git revert` del merge (la API es aditiva).

## Amendment 2026-09-16 (review whole-branch)

Tres huecos del contrato "argumento inválido → error accionable; lista vacía solo si no hay
resultados reales" que la implementación no cerraba todavía, corregidos sin cambiar la decisión de
diseño (detalle en spec §4.6):

- `Retriever.retrieve` tragaba el fallo del proveedor de embeddings y devolvía `[]`; ahora propaga
  (`EmbeddingUnavailableError`) y `/api/search/semantic` responde 503 `EMBEDDING_UNAVAILABLE`, igual
  que `/api/stats/trend`. `src/rag/chat.py` lo traduce a un evento SSE `error` en vez de propagar
  (canal propio de streaming) — decisión: fallar ruidoso ahí también, no seguir con una respuesta
  del LLM sin contexto real.
- `GET /api/items/{id}/similar` devolvía `EMBEDDING_NOT_FOUND` para un id inexistente sin comprobar
  si el item existía; el cliente MCP lo traducía a un mensaje falso ("item exists but..."). Ahora
  distingue `NOT_FOUND` (404, no existe) de `EMBEDDING_NOT_FOUND` (404, existe sin embedding).
- `search` (MCP y API) aceptaba `date_from > date_to` y devolvía una lista vacía; ahora rechaza con
  un error accionable antes de tocar la API. `q` gana `max_length=200` en las tres superficies
  (`/api/search`, `/api/search/semantic`, tool `search`).
