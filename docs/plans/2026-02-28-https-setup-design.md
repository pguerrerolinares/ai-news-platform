# HTTPS Setup via Coolify/Traefik

**Date**: 2026-02-28
**Status**: Approved

## Problem

The production site at `pguerrero.me` is served over HTTP only. Need to enable HTTPS
with automatic certificate management.

## Decision

Use Coolify's built-in Traefik reverse proxy for SSL termination with Let's Encrypt.
This is the simplest approach since the app is already deployed via Coolify on a Hetzner VPS.

## Architecture

```
Internet -> HTTPS:443 -> Traefik (SSL termination, Let's Encrypt) -> frontend nginx:80 -> /api/* -> api:8000
         -> HTTP:80   -> Traefik -> 301 redirect -> HTTPS
```

- Traefik handles certificate issuance, renewal, and HTTP->HTTPS redirect
- Internal container traffic remains HTTP (normal for container networks)
- `docker-compose.coolify.yml` requires no changes (already configured for Traefik)

## Changes

### Code change (1 file)

**`frontend/nginx.conf`** — Add HSTS header:
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### Coolify UI configuration

1. Service -> Domains -> set `https://pguerrero.me`
2. Environment Variables -> `CORS_ORIGINS=https://pguerrero.me`
3. Redeploy

### Verification

1. `curl -I https://pguerrero.me` — should return 200 with HSTS header
2. `curl -I http://pguerrero.me` — should return 301 redirect to HTTPS
3. Test SSE chat endpoint works over HTTPS
4. Check certificate validity with `openssl s_client -connect pguerrero.me:443`

## Alternatives considered

| Approach | Pros | Cons |
|----------|------|------|
| **A: Coolify/Traefik (chosen)** | Zero infra changes, auto-renewal, managed | Tied to Coolify |
| B: Certbot on VPS | Full control | Manual renewal, lose Coolify dashboard |
| C: Cloudflare proxy | CDN + DDoS protection | Nameserver change, flexible mode = HTTP backend |
