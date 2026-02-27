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

If deploying via Coolify (`docker-compose.coolify.yml`), Traefik handles SSL automatically:

1. In Coolify UI → your service → **Domains** → enter `https://pguerrero.me`
2. In Coolify UI → **Environment Variables** → set `CORS_ORIGINS=https://pguerrero.me`
3. Click **Redeploy**
4. Verify:
   ```bash
   # Should return 200 with Strict-Transport-Security header
   curl -I https://pguerrero.me

   # Should return 301 redirect to HTTPS
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
