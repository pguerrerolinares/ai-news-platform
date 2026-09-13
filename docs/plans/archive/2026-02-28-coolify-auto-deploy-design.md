# Coolify Auto-Deploy Configuration Design

**Date:** 2026-02-28
**Status:** Approved
**Type:** Configuration (no code changes)

## Problem

The CI pipeline (`ci.yml`) has a deploy stage that triggers a Coolify webhook after all tests pass, but the required GitHub secrets and variables are not configured. Deploys to production (`pguerrero.me`) are currently manual.

## Goal

When a push to `main` passes all CI stages (lint, typecheck, test, integration), automatically trigger a Coolify redeploy via its webhook API.

## Existing Infrastructure

- **CI workflow:** `.github/workflows/ci.yml` — 4 stages + deploy stage already defined
- **Deploy compose:** `docker-compose.coolify.yml` — Traefik + 4 services (db, api, frontend, pipeline-cron)
- **VPS:** Hetzner CX22 at `89.167.115.45`, Coolify installed, service already deployed
- **Domain:** `pguerrero.me` with HTTPS via Traefik + Let's Encrypt

## Existing Deploy Stage (no changes needed)

```yaml
deploy:
  name: Deploy to Coolify
  needs: [integration]
  if: github.ref == 'refs/heads/main' && github.event_name == 'push' && vars.COOLIFY_DEPLOY_ENABLED == 'true'
  steps:
    - name: Trigger Coolify deploy
      run: |
        curl -f -X POST "${{ secrets.COOLIFY_WEBHOOK }}" \
          -H "Authorization: Bearer ${{ secrets.COOLIFY_TOKEN }}" \
          -H "Content-Type: application/json" \
          --max-time 10
        echo "Deploy triggered successfully"
```

## Configuration Steps

### Step 1: Generate Coolify API Token

1. Open Coolify dashboard
2. Navigate to **Settings > API Tokens**
3. Click **Generate new token**, name it `github-actions`
4. Copy the token value (shown only once)

### Step 2: Get Coolify Webhook URL

1. In Coolify dashboard, go to your **ai-news-platform** service
2. Navigate to the **Webhooks** tab
3. Copy the deploy webhook URL
   - Format: `https://<coolify-domain>/api/v1/deploy?uuid=<service-uuid>&force=false`

### Step 3: Configure GitHub Secrets

1. Go to GitHub repo **Settings > Secrets and variables > Actions**
2. Add **Repository Secret**: `COOLIFY_WEBHOOK` = webhook URL from Step 2
3. Add **Repository Secret**: `COOLIFY_TOKEN` = API token from Step 1
4. Add **Repository Variable**: `COOLIFY_DEPLOY_ENABLED` = `true`

## Safety Mechanisms

| Mechanism | Description |
|-----------|-------------|
| Branch gate | Only triggers on `main` branch pushes (not PRs) |
| CI gate | Only triggers after all 4 stages pass (lint, typecheck, test, integration) |
| Kill switch | Set `COOLIFY_DEPLOY_ENABLED` to `false` to disable instantly |
| Timeout | `--max-time 10` prevents hanging on unresponsive Coolify |
| Failure flag | `curl -f` fails the step on HTTP errors |

## Rollback

- **Via Coolify UI:** Redeploy a previous version from the deployment history
- **Via git:** Revert the commit on main, CI will re-run and deploy the reverted state

## Deploy Flow

```
Push to main
  -> lint (parallel with typecheck)
  -> typecheck
  -> test (needs lint + typecheck)
  -> integration (needs test)
  -> deploy webhook (needs integration, only on main push)
  -> Coolify pulls code, builds images, restarts containers
```

## Alternatives Considered

1. **SSH-based deploy:** More control but requires SSH key management, bypasses Coolify's UI/logs/rollback features
2. **Coolify Git Integration (auto-deploy on push):** Simpler but bypasses CI — would deploy even if tests fail
