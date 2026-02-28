# Deployment Runbook

## Initial VPS Setup (Hetzner CX22)

### 1. Server Provisioning
```bash
# After creating VPS in Hetzner console:
ssh root@YOUR_VPS_IP

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt install docker-compose-plugin -y

# Create deploy user
useradd -m -s /bin/bash deploy
usermod -aG docker deploy

# Setup SSH key for deploy user
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
```

### 2. Clone Repository
```bash
su - deploy
git clone <REPO_URL> /opt/ai-news-platform
cd /opt/ai-news-platform
cp .env.example .env
# Edit .env with production values
```

### 3. Domain + SSL (direct docker-compose.yml)
```bash
# Point domain A record to VPS IP first, then:
docker compose --profile certbot run certbot certonly \
  --webroot -w /var/www/certbot \
  -d YOUR_DOMAIN --email YOUR_EMAIL --agree-tos

# Enable HTTPS in nginx.conf (uncomment HTTPS server block)
# Update YOUR_DOMAIN placeholders
docker compose restart nginx
```

### 3b. Domain + SSL (Coolify deployment)

If deploying via Coolify (`docker-compose.coolify.yml`), Traefik handles SSL via labels in the compose file.

**Prerequisites:**
1. Traefik proxy must be **running** in Coolify (Servers → localhost → Proxy → Start)
2. The `coolify` Docker network must exist and have IPv6 **disabled** (see Troubleshooting)
3. "Connect to Predefined Network" must be **enabled** in the service settings

**How it works:**
- `docker-compose.coolify.yml` has Traefik labels on the `frontend` service
- Frontend uses `expose: "80"` (NOT `ports`) so traffic routes through Traefik
- Traefik terminates SSL with Let's Encrypt and forwards to nginx on port 80
- HTTP requests are redirected to HTTPS via middleware

**Configuration:**
1. In Coolify UI → **Environment Variables** → set `CORS_ORIGINS=https://pguerrero.me`
2. Click **Redeploy**
3. Verify:
   ```bash
   # Should return 200 with Strict-Transport-Security header
   curl -I https://pguerrero.me

   # Should return 307 redirect to HTTPS
   curl -I http://pguerrero.me

   # SSE chat endpoint (requires auth token)
   curl -N -H "Authorization: Bearer <token>" https://pguerrero.me/api/chat

   # Certificate check
   openssl s_client -connect pguerrero.me:443 -brief
   ```

### 4. Start Services
```bash
cd /opt/ai-news-platform
docker compose up -d
docker compose exec api alembic upgrade head
./scripts/health_check.sh
```

### 5. Setup Cron
```bash
# Daily pipeline at 8:00 UTC
crontab -e
# Add: 0 8 * * * cd /opt/ai-news-platform && docker compose --profile pipeline run --rm pipeline

# Daily backup at 2:00 UTC
# Add: 0 2 * * * cd /opt/ai-news-platform && ./scripts/backup.sh

# SSL renewal monthly
# Add: 0 0 1 * * cd /opt/ai-news-platform && docker compose --profile certbot run certbot renew && docker compose restart nginx
```

## Routine Deploy (Automated via GitHub Actions)

Push to main -> CI passes -> CD deploys automatically.

## Manual Deploy
```bash
ssh deploy@YOUR_VPS
cd /opt/ai-news-platform
git pull origin main
docker compose build --no-cache api
docker compose up -d api
docker compose exec api alembic upgrade head
./scripts/health_check.sh
```

## Rollback
```bash
# Check previous version
cat .prev_version

# Rollback to specific commit
git checkout <COMMIT_SHA> -- .
docker compose build --no-cache api
docker compose up -d api
```

## Troubleshooting: Coolify + Traefik

### Traefik won't start: IPv6 ParseAddr error

**Symptom:** `ParseAddr("fdcc:...::1/64"): unexpected character, want colon`

**Cause:** The `coolify` Docker network has IPv6 enabled, and Traefik v3.x can't parse IPv6 addresses with CIDR notation.

**Fix:**
```bash
# 1. Disconnect all containers from the coolify network
for c in $(docker network inspect coolify -f '{{range .Containers}}{{.Name}} {{end}}'); do
  docker network disconnect -f coolify "$c" 2>/dev/null
done

# 2. Recreate without IPv6
docker network rm coolify
docker network create coolify --driver bridge

# 3. Reconnect Coolify's own containers (CRITICAL — do this immediately!)
docker network connect coolify coolify
docker network connect coolify coolify-db
docker network connect coolify coolify-redis
docker network connect coolify coolify-realtime
docker network connect coolify coolify-sentinel
docker restart coolify coolify-db coolify-redis coolify-realtime coolify-sentinel

# 4. Start Traefik from Coolify UI (Servers → localhost → Proxy → Start)
# 5. Redeploy your app to reconnect its containers to the network
```

### Site down after changing ports→expose

**Symptom:** Neither HTTP nor HTTPS responds after changing `ports: "80:80"` to `expose: "80"`.

**Cause:** Traefik proxy is not running. Without Traefik, `expose` only makes the port visible within the Docker network — no host binding.

**Fix:** Start Traefik in Coolify (Servers → localhost → Proxy → Start), then redeploy.

**Prevention:** Always verify Traefik is running before switching from `ports` to `expose`:
```bash
docker ps | grep coolify-proxy
```

### POSTGRES_PASSWORD mismatch after changing password

**Symptom:** API container is unhealthy, logs show authentication errors.

**Cause:** `POSTGRES_PASSWORD` env var only sets the password on first DB initialization. If the volume already exists, PostgreSQL ignores the env var.

**Fix:**
```bash
# Enter the DB container
docker exec -it $(docker ps -qf "ancestor=pgvector/pgvector:pg16") bash

# Inside the container: temporarily allow passwordless access
sed -i 's/scram-sha-256/trust/g' /var/lib/postgresql/data/pg_hba.conf
su - postgres -c "/usr/lib/postgresql/16/bin/pg_ctl reload -D /var/lib/postgresql/data"

# Change password to match the env var
psql -U ainews -d ainews -c "ALTER USER ainews WITH PASSWORD 'NEW_PASSWORD';"

# Restore secure authentication
sed -i 's/trust/scram-sha-256/g' /var/lib/postgresql/data/pg_hba.conf
su - postgres -c "/usr/lib/postgresql/16/bin/pg_ctl reload -D /var/lib/postgresql/data"
exit
```
Then redeploy in Coolify.

### Duplicate env vars in Coolify

**Symptom:** Coolify shows two entries for the same variable (e.g., two `POSTGRES_PASSWORD` with different values).

**Cause:** Coolify creates separate entries for each `${VAR}` reference in the compose file. If `POSTGRES_PASSWORD` appears in `db`, `api`, and `pipeline-cron` services, Coolify may create duplicates.

**Prevention:** Only set each variable once in Coolify's Environment Variables. Delete duplicates immediately if they appear — the last value wins and may cause mismatches.

### Browser shows "not secure" after enabling HTTPS

**Symptom:** HTTPS works (valid cert) but browser shows "not secure" warning.

**Cause:** Browser cached the HTTP version from before the migration.

**Fix:** Clear browser cache for the domain, or open in incognito. The HSTS header (`max-age=31536000`) will force HTTPS for future visits automatically.
