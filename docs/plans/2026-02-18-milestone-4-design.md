# Milestone 4 — RAG + Q&A Design

## Goal

Add a "ask about AI news" chat feature: embed news items with OpenAI, store vectors in pgvector, retrieve relevant context via cosine similarity, and stream LLM answers via Kimi/Moonshot through an Angular chat page.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Embedding provider | OpenAI `text-embedding-3-small` (1536 dims) | Best quality/cost ratio, uses existing `openai` package |
| Chat LLM | Kimi/Moonshot (existing config) | Already configured, zero extra cost |
| Streaming | SSE (Server-Sent Events) | Better UX, tokens appear in real-time |
| Historical import | Skipped (YAGNI) | Focus on new items; backfill can be added later |
| Conversation memory | No (single-turn) | News Q&A is self-contained; multi-turn is YAGNI |
| Vector index | HNSW (cosine) | Fast approximate nearest-neighbor, good for <1M vectors |

## Architecture

Simple RAG pipeline:

```
User question
  -> embed query (OpenAI text-embedding-3-small)
  -> pgvector cosine search (top-K items)
  -> build prompt with retrieved context
  -> stream Kimi/Moonshot response (SSE)
  -> display in Angular chat page
```

No conversation history. No re-ranking. No LangChain/LlamaIndex (raw OpenAI + pgvector + SQLAlchemy).

## Components

### 1. Database (Migration 002)

Alter `item_embeddings.embedding` from `Text` placeholder to `vector(1536)`. Create HNSW index:

```sql
ALTER TABLE item_embeddings
  ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536);

CREATE INDEX ix_item_embeddings_hnsw ON item_embeddings
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

Update `ItemEmbedding` ORM model to use `Vector(1536)` from `pgvector.sqlalchemy`.

### 2. Config (new settings)

```python
embedding_api_key: str = ""          # OpenAI API key (separate from Kimi)
embedding_base_url: str = "https://api.openai.com/v1"
embedding_model: str = "text-embedding-3-small"
embedding_dimensions: int = 1536
```

### 3. Embedding Service (`src/rag/embeddings.py`)

- `embed_text(text: str) -> list[float]` — embed a single query string
- `embed_items(session, items: list[NewsItem]) -> int` — batch embed and store
- Input format: `"{title}\n{summary}"` (truncated to 8191 tokens)
- Batch size: up to 100 items per API call
- Uses `openai.AsyncOpenAI(api_key=embedding_api_key, base_url=embedding_base_url)`

### 4. Retriever (`src/rag/retriever.py`)

- `retrieve(session, query: str, limit=5, topic=None) -> list[NewsItem]`
- Embeds query via `embed_text()`
- SQL: `SELECT ... FROM news_items JOIN item_embeddings ON ... ORDER BY embedding <=> :query_vec LIMIT :k`
- Optional topic filter

### 5. Chat Service (`src/rag/chat.py`)

- `chat_stream(session, question, topic=None, limit=5) -> AsyncGenerator[str, None]`
- Retrieves context via retriever
- System prompt (Spanish):

```
Eres un asistente experto en noticias de IA y tecnologia.
Responde basandote SOLO en las noticias proporcionadas como contexto.
Si no hay informacion relevante, dilo claramente.
Incluye las fuentes (titulos y URLs) en tu respuesta.
```

- Streams via Kimi with `stream=True`
- SSE format: `data: {"token": "..."}\n\n`
- Final event: `data: {"sources": [{"id", "title", "url"}]}\n\n` then `data: [DONE]\n\n`

### 6. API Endpoint (`src/api/routes/chat.py`)

```
POST /api/chat
Body: {"question": str, "topic": str | null, "limit": int = 5}
Response: StreamingResponse(media_type="text/event-stream")
Auth: require_auth (JWT Bearer)
Rate limit: 10/min
```

### 7. Angular Chat Page (`web/src/app/pages/chat.ts`)

- Route: `/chat` (protected by authGuard)
- UI: message list + input field + send button at bottom
- Streaming via `fetch()` + `ReadableStream` (not EventSource, since POST is needed)
- Token-by-token rendering into the answer area
- Sources displayed as clickable links below each answer
- Optional topic filter dropdown
- Nav link: "Chat" between "Analytics" and "Salir"

### 8. Pipeline Integration

New step 9 in `run_pipeline()` after item storage:

- Query items without embeddings
- Batch embed via embedding service
- Only runs if `embedding_api_key` is set
- Errors logged but don't fail the pipeline

## File Map

| File | Action |
|---|---|
| `alembic/versions/002_add_vector_embedding.py` | Create |
| `src/core/config.py` | Modify (add embedding settings) |
| `src/core/models.py` | Modify (update ItemEmbedding.embedding to Vector) |
| `src/rag/__init__.py` | Modify (exports) |
| `src/rag/embeddings.py` | Create |
| `src/rag/retriever.py` | Create |
| `src/rag/chat.py` | Create |
| `src/api/routes/chat.py` | Create |
| `src/api/app.py` | Modify (include chat router) |
| `src/pipeline/pipeline.py` | Modify (add step 9) |
| `web/src/app/pages/chat.ts` | Create |
| `web/src/app/app.routes.ts` | Modify (add /chat route) |
| `web/src/app/app.ts` | Modify (add Chat nav link) |
| `web/src/app/services/news.service.ts` | Modify (or new chat.service.ts) |
| `tests/unit/test_embeddings.py` | Create |
| `tests/unit/test_retriever.py` | Create |
| `tests/unit/test_chat.py` | Create |
| `tests/unit/test_chat_route.py` | Create |
| `tests/e2e/test_chat.py` | Create |

## Verification

1. `pytest tests/unit/` — all unit tests pass (including new RAG tests)
2. `pytest tests/e2e/` — chat E2E tests pass
3. Embeddings generated for items during pipeline run
4. `POST /api/chat` streams a coherent answer with sources
5. Angular chat page renders streaming tokens
6. Question "What AI models were released?" returns relevant items
