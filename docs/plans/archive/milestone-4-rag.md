# Milestone 4 — RAG + Q&A

**Objective**: "Ask me about AI news" works.

## Tasks

- [ ] Decide embedding model (Moonshot if available, else Jina/alternative)
- [ ] Generate embeddings during pipeline run
- [ ] Vector index in pgvector (HNSW or IVFFlat)
- [ ] `POST /api/chat` endpoint: embed query -> vector search -> LLM answer
- [ ] Angular chat page (input + streaming response)
- [ ] Import script for curated historical datasets (2023-2026)
- [ ] Seed embeddings for historical data
- [ ] Tests, docs

## Verification

1. Embeddings generated for all items in DB
2. `POST /api/chat` returns coherent answer
3. Chat UI works in Angular
4. Historical data imported (2023-2026)
5. Ask "What models were released last week?" returns real data
