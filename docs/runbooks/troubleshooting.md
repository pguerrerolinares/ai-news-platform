# Troubleshooting

## Common Issues

### Database Connection Failed
**Symptom**: `/health` returns `{"status": "unhealthy", "database": "..."}`

**Fixes**:
1. Check PostgreSQL is running: `docker compose ps db`
2. Check logs: `docker compose logs db`
3. Verify `.env` credentials match docker-compose.yml
4. Test connection: `docker compose exec db psql -U ainews ainews -c "SELECT 1"`

### Pipeline Returns 0 Items
**Symptom**: a `pipeline_runs` row shows 0 items extracted/stored (check via admin freshness/audit endpoints or pipeline logs)

**Fixes**:
1. Check source API is accessible from VPS: `curl -sf https://hn.algolia.com/api/v1/search?query=AI`
2. Check pipeline logs: `docker compose --profile pipeline logs pipeline`
3. Run manually with debug: `DEBUG=true docker compose --profile pipeline run --rm pipeline`
4. Verify extractor config in `.env` (queries, time windows)

### Deploy Failed / Health Check Timeout
**Symptom**: Coolify deployment marked failed, or the container health check never turns healthy

**Fixes**:
1. Check API logs: `docker compose logs api --tail=50`
2. Check if port 8000 is in use: `docker compose ps`
3. Run health check manually: `curl -sf http://localhost:8000/health`
4. Check if migration failed: `docker compose exec api alembic current`
5. Rollback: `cat .prev_version` then `git checkout <SHA> -- . && docker compose up -d api`

### Alembic Migration Failed
**Symptom**: `alembic upgrade head` errors

**Fixes**:
1. Check current revision: `docker compose exec api alembic current`
2. Check migration history: `docker compose exec api alembic history`
3. If stuck, check for lock: `docker compose exec db psql -U ainews -c "SELECT * FROM alembic_version"`
4. Rollback migration: `docker compose exec api alembic downgrade -1`

### High Memory Usage
**Symptom**: OOM killer or services restarting

**Fixes**:
1. Check memory: `docker stats --no-stream`
2. Reduce API workers in `.env`: `API_WORKERS=1`
3. Reduce PostgreSQL shared_buffers
4. Check for memory leaks in pipeline (large item batches)

### MCP Container Restarting Silently (RestartCount climbing, ExitCode=0)
**Symptom**: `mcp` service `RestartCount` climbs over days/weeks with `docker inspect` showing
`ExitCode=0` / `OOMKilled=false` for the *current* container state — misleading, because
`docker events`'s in-memory ring buffer only retains recent activity and the per-container
counters reset on every redeploy, so by the time anyone looks, the evidence of the actual kill
is gone from `docker inspect`/`docker events`.

**Root cause (found 2026-09-13, see ADR and commit on `fix/mcp-healthcheck`)**: the `mcp` service
had `deploy.resources.limits.memory: 256M` in `docker-compose.coolify.yml`, but the FastMCP/
Starlette/httpx stack's steady-state RSS sits at ~248-250MiB — leaving only ~3MiB of headroom.
The kernel's memcg OOM killer fired at least 3 times in two weeks (`journalctl -k`):
```
Sep 03 20:45:07 kernel: python invoked oom-killer ... Killed process ... (python) ... anon-rss:248668kB
Sep 08 00:55:15 kernel: python invoked oom-killer ... Killed process ... (python) ... anon-rss:247364kB
Sep 12 05:11:22 kernel: curl invoked oom-killer   ... Killed process ... (python) ... anon-rss:248204kB
```
Each kill is `constraint=CONSTRAINT_MEMCG` scoped to the `mcp` container's own cgroup (only `mcp`
declares a `memory:` limit in the compose file — every other service is uncapped), `uid=1000`
(the `appuser` from `Dockerfile.mcp`), and the victim is the main `python -m src.mcp.server`
process. On 2026-09-12 the allocating process that tipped the cgroup over the edge was `curl` —
i.e. the (now-fixed) unfalsifiable healthcheck's own `docker exec curl ...`, which shares the
container's cgroup, was occasionally enough by itself to trigger the kill. `unless-stopped`
then restarts the container immediately, so nothing outside the kernel ring buffer records it.

**Fix applied**: raised `memory: 256M` → `512M` for `mcp` in `docker-compose.coolify.yml` (real
headroom; host has 3.7GiB total / ~1.7GiB free at time of writing).

**Not fully explained**: why steady-state RSS is ~250MiB in the first place (vs. ~50MiB right
after a fresh start) — could be normal working-set growth (session cache, httpx connection
pool, import overhead) or a genuine slow leak; the three data points are too close together in
magnitude to tell apart from kernel logs alone. If restarts recur even at 512M, profile the
process (`docker exec <mcp> python -c "import resource; print(resource.getrusage(...))"` over
time, or `tracemalloc`) rather than raising the limit again.

**Diagnose**:
1. `journalctl -k --since '<window>' | grep -iE 'oom-killer|Killed process'` — kernel ring buffer
   evidence survives container recreation (unlike `docker events`/`docker inspect`).
2. `docker inspect <container> --format '{{.HostConfig.Memory}}'` to confirm which service has a
   cap.
3. `docker stats --no-stream <container>` for current usage vs. limit.

### SSL Certificate Renewal Failed
**Symptom**: Browser shows certificate expired

**Fixes**:
```bash
docker compose --profile certbot run certbot renew
docker compose restart nginx
```

## Log Locations

| Service | Command |
|---------|---------|
| API | `docker compose logs api` |
| Pipeline | `docker compose --profile pipeline logs pipeline` |
| Database | `docker compose logs db` |
| Nginx | `docker compose logs nginx` |

## Useful Commands

```bash
# Check all service status
docker compose ps

# Check resource usage
docker stats --no-stream

# Access database CLI
docker compose exec db psql -U ainews ainews

# Count items by source
docker compose exec db psql -U ainews ainews -c "SELECT source, count(*) FROM news_items GROUP BY source"

# Recent items
docker compose exec db psql -U ainews ainews -c "SELECT title, source, created_at FROM news_items ORDER BY created_at DESC LIMIT 10"

# Run one-off pipeline
docker compose --profile pipeline run --rm pipeline
```
