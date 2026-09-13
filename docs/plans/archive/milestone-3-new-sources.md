# Milestone 3 — New Sources + MCP Server + Polish

**Objective**: More sources, MCP server for agent consumption, monitoring, polished UI.

## Tasks

### New Sources
- [ ] GitHub Trending extractor (GitHub Search API, stars >100 recent, AI/ML topic)
- [ ] HuggingFace extractor (HF API, popular models/datasets)

### MCP Server
- [ ] MCP server with stdio transport (runs LOCAL, calls FastAPI via HTTPS)
- [ ] Tool: `search_news(query, topic?, date_from?, date_to?, min_dev_value?)`
- [ ] Tool: `get_latest(topic?, limit=10)`
- [ ] Tool: `get_trending()`
- [ ] Tool: `get_tech_status(technology)`
- [ ] Auth: JWT token in headers
- [ ] Documentation for Claude Code setup
- [ ] Publishable package or clear install instructions

### Polish
- [ ] Monitoring: Telegram alerts for all failure modes
- [ ] Frontend charts: items/day, topic distribution, trends
- [ ] Rate limiting (slowapi)
- [ ] CORS configuration
- [ ] Responsive frontend (mobile)
- [ ] Tests, docs

## Verification

1. 6 sources active
2. MCP server works in Claude Code: `search_news("latest LLM releases")` returns results
3. `dev_value_score` assigned by LLM
4. Telegram alerts on all failure modes
5. Frontend responsive on mobile
6. Rate limiting active
