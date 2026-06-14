# Migración ai-news → /ai-news

## URLs nuevas
- Web: https://pguerrero.me/ai-news
- API: https://pguerrero.me/ai-news/api (interno, vía nginx del frontend)
- MCP: https://pguerrero.me/ai-news/mcp  ← antes /mcp

## Acción requerida en clientes MCP
Reapuntar la config del cliente (Claude Code `.mcp.json` / settings) de
`https://pguerrero.me/mcp` a `https://pguerrero.me/ai-news/mcp`.

## Cómo funciona (Traefik StripPrefix)
- `StripPrefix(/ai-news)` en Traefik: los contenedores siguen recibiendo `/`, `/api`, `/mcp`.
- Frontend: router `ainews-fe-https` con `PathPrefix(/ai-news)` + `ainews-fe-strip`, priority 50.
- MCP: router `mcp-https` con `PathPrefix(/ai-news/mcp)` + `mcp-strip`, priority 100 (> 50 para no caer en el SPA).
- Routers HTTP equivalentes con redirect a HTTPS (`frontend-redirect`).
- Backend FastAPI y MCP: **sin cambios de código** (siguen sirviendo /, /api, /mcp).
- Frontend build: `PUBLIC_BASE_PATH=/ai-news/` (base de Vite + basename del router) y `VITE_API_URL=/ai-news` (api.ts → /ai-news/api).
- Auth: tokens en localStorage (no cookies) → sin impacto en sesiones ni WebAuthn (RP ID = dominio).

## Verificación post-corte (por CONTENIDO, no por status code)
> El SPA devuelve 200 para cualquier ruta (catch-all de nginx). Un `curl -sI` da falsos positivos.
- `/ai-news` → el HTML debe referenciar `/ai-news/assets/...` (no `/assets/...`).
- `/ai-news/mcp` → respuesta del MCP (406/JSON), no el `index.html` del SPA.
- `/` → web nueva (marcador del HTML de Astro), no el SPA de ai-news.
