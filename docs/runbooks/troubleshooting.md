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
**Symptom**: Telegram alert "extractor returned 0 items"

**Fixes**:
1. Check source API is accessible from VPS: `curl -sf https://hn.algolia.com/api/v1/search?query=AI`
2. Check pipeline logs: `docker compose --profile pipeline logs pipeline`
3. Run manually with debug: `DEBUG=true docker compose --profile pipeline run --rm pipeline`
4. Verify extractor config in `.env` (queries, time windows)

### Deploy Failed / Health Check Timeout
**Symptom**: Telegram alert "Deploy FAILED"

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
