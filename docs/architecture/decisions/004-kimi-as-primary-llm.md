# ADR-004: Kimi/Moonshot as Primary LLM

## Status: Accepted
## Date: 2026-02-17

## Context
The platform needs LLM capabilities for: (1) content classification and summarization, (2) event deduplication, (3) eventually RAG Q&A. We evaluated OpenAI, Anthropic, Gemini, and Kimi/Moonshot.

## Decision
Kimi/Moonshot API as the primary LLM, accessed via the OpenAI-compatible API.

## Consequences
**Pros:**
- Cheapest option among evaluated providers
- OpenAI-compatible API (uses `openai` Python SDK)
- Already configured and proven in predecessor project
- Sufficient quality for classification and summarization
- Easy to switch to another provider (same API format)

**Cons:**
- Less powerful than GPT-4 or Claude for complex reasoning
- Less well-known, smaller community
- API reliability unknown at scale (though predecessor has been stable)
- May need to evaluate alternatives for embeddings (Milestone 4)
