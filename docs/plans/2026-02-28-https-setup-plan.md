# HTTPS Setup via Coolify/Traefik — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable HTTPS on production via Coolify's Traefik reverse proxy with a single code change and UI configuration.

**Architecture:** Traefik (managed by Coolify) handles SSL termination with Let's Encrypt. The only code change is adding HSTS + security headers to `frontend/nginx.conf`. CORS and domain are configured in Coolify UI.

**Tech Stack:** Nginx, Traefik (Coolify-managed), Let's Encrypt

**Design doc:** `docs/plans/2026-02-28-https-setup-design.md`

---

### Task 1: Add security headers to frontend nginx.conf

**Files:**
- Modify: `frontend/nginx.conf:1-5` (add headers after `index` directive)

**Step 1: Add HSTS and security headers**

Edit `frontend/nginx.conf` to add security headers inside the `server` block, after line 5 (`index index.html;`):

```nginx
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

These match what's already in the root `nginx.conf` (line 31-33) plus HSTS for HTTPS.

**Step 2: Validate nginx config syntax**

Run: `docker run --rm -v $(pwd)/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:1.27-alpine nginx -t`
Expected: `nginx: the configuration file /etc/nginx/nginx.conf syntax is ok`

**Step 3: Commit**

```bash
git add frontend/nginx.conf
git commit -m "feat: add HSTS and security headers to frontend nginx

Prepares frontend nginx for HTTPS deployment via Coolify/Traefik.
Adds Strict-Transport-Security, X-Frame-Options, X-Content-Type-Options,
and Referrer-Policy headers matching the root nginx.conf."
```

---

### Task 2: Update deployment runbook with Coolify HTTPS steps

**Files:**
- Modify: `docs/runbooks/deployment.md` (add Coolify HTTPS section)

**Step 1: Add Coolify HTTPS section**

Add a new section after "### 3. Domain + SSL" in `docs/runbooks/deployment.md`:

```markdown
### 3b. Domain + SSL (Coolify deployment)

If deploying via Coolify (`docker-compose.coolify.yml`), Traefik handles SSL automatically:

1. In Coolify UI → your service → **Domains** → enter `https://pguerrero.me`
2. In Coolify UI → **Environment Variables** → set `CORS_ORIGINS=https://pguerrero.me`
3. Click **Redeploy**
4. Verify:
   - `curl -I https://pguerrero.me` → 200 with `Strict-Transport-Security` header
   - `curl -I http://pguerrero.me` → 301 redirect to HTTPS
   - Test SSE chat endpoint: `curl -N https://pguerrero.me/api/chat`
   - Certificate check: `openssl s_client -connect pguerrero.me:443 -brief`
```

**Step 2: Commit**

```bash
git add docs/runbooks/deployment.md
git commit -m "docs: add Coolify HTTPS setup steps to deployment runbook"
```

---

### Task 3: Configure Coolify and verify (manual, in production)

This task is performed manually in the Coolify UI, not via code.

**Step 1: Set HTTPS domain in Coolify**

- Open Coolify dashboard → your ai-news-platform service
- Go to **Domains** field
- Change from `http://pguerrero.me` to `https://pguerrero.me`

**Step 2: Update CORS_ORIGINS**

- In Coolify → Environment Variables
- Change `CORS_ORIGINS=http://pguerrero.me` to `CORS_ORIGINS=https://pguerrero.me`

**Step 3: Redeploy**

- Click Redeploy in Coolify (or push to trigger auto-deploy after committing tasks 1-2)

**Step 4: Verify HTTPS works**

```bash
# Should return 200 with HSTS header
curl -I https://pguerrero.me

# Should return 301 redirect
curl -I http://pguerrero.me

# SSE chat should stream over HTTPS
curl -N -H "Authorization: Bearer <token>" https://pguerrero.me/api/chat

# Certificate should be valid Let's Encrypt
openssl s_client -connect pguerrero.me:443 -brief
```

**Step 5: Test the full app**

- Login flow works over HTTPS
- Dashboard loads
- Chat SSE streaming works
- API calls return data

---

## Summary

| Task | Type | Effort |
|------|------|--------|
| 1. Security headers in nginx | Code | ~2 min |
| 2. Update deployment runbook | Docs | ~2 min |
| 3. Coolify UI config + verify | Manual/Ops | ~5 min |
