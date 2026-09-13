---
name: Docker Multi-Stage Stack Builder
description: Containerizes web applications and dependencies into lightweight, production-ready multi-stage Docker images orchestrated via Docker Compose.
metadata:
  source: skills/docker-multi-stage-stack-builder/docker-multi-stage-stack-builder.md
---

# Docker Multi-Stage Stack Builder

## 1. System Architecture & Prerequisites

This skill builds a complete production stack: a **multi-stage Next.js Docker image** (<100MB target), **PostgreSQL**, **Redis**, and an **Nginx reverse proxy** — all orchestrated via Docker Compose with health checks, volume persistence, and dependency ordering.

**Architecture layers:**

```
[Client] → [nginx:1.27-alpine] → [next-app:standalone] → [PostgreSQL 16] + [Redis 7]
```

**Prerequisites:**

- Docker ≥ 24 & Docker Compose V2 (`docker compose` plugin)
- Node.js ≥ 18 (for local development only)
- A working Next.js project with `output: "standalone"` in `next.config.ts`

## 2. Input/Output Data Contracts

**Input — Environment Variables (.env.example):**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["POSTGRES_PASSWORD", "NEXTAUTH_SECRET"],
  "properties": {
    "POSTGRES_USER": { "type": "string", "default": "appuser" },
    "POSTGRES_PASSWORD": { "type": "string", "description": "Strong password for PostgreSQL" },
    "POSTGRES_DB": { "type": "string", "default": "appdb" },
    "DATABASE_URL": { "type": "string", "description": "Full postgres:// connection string" },
    "REDIS_URL": { "type": "string", "default": "redis://redis:6379" },
    "NEXTAUTH_SECRET": { "type": "string", "description": "Auth secret for Next.js" },
    "NEXTAUTH_URL": { "type": "string", "default": "http://localhost:3000" },
    "NODE_ENV": { "type": "string", "default": "production" }
  }
}
```

**Output Artifacts:**

| Path | Description |
|---|---|
| `Dockerfile` | Multi-stage build (base → deps → build → runner) |
| `.dockerignore` | Build context exclusions |
| `docker-compose.yml` | Full stack orchestration |
| `nginx/nginx.conf` | Reverse proxy configuration |
| `nginx/Dockerfile` | Nginx build with config baked in |
| `.env.example` | Template environment file |
| `scripts/entrypoint.sh` | Container entrypoint script |

## 3. Production Reference Implementation

```dockerfile
# Dockerfile — Multi-stage Next.js build targeting <100MB final image

# ── Stage 1: Base dependencies ──────────────────────────────────
FROM node:20-alpine AS base
RUN apk add --no-cache libc6-compat
ENV NODE_ENV=production
WORKDIR /app

# ── Stage 2: Install dependencies ───────────────────────────────
FROM base AS deps
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev && \
    npm cache clean --force

# ── Stage 3: Build application ──────────────────────────────────
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Ensure Next.js uses standalone output mode
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 4: Production runner ──────────────────────────────────
FROM node:20-alpine AS runner

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy only what's needed for standalone mode
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Non-root user
USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NODE_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
```

```dockerignore
# .dockerignore

# Dependencies
node_modules
.npm

# Build artifacts
.next
out
dist
build
coverage

# Environment & secrets
.env
.env.*
!.env.example

# Development files
.git
.gitignore
.vscode
.idea
*.md
!README.md
Dockerfile
docker-compose*.yml
.dockerignore

# OS files
.DS_Store
Thumbs.db
```

```yaml
# docker-compose.yml
version: "3.9"

services:
  # ── PostgreSQL ───────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: app-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-appuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-appdb}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-appuser} -d ${POSTGRES_DB:-appdb}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - backend

  # ── Redis ───────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: app-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 5s
    networks:
      - backend

  # ── Next.js Application ─────────────────────────────────────
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runner
    container_name: app-web
    restart: unless-stopped
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://${POSTGRES_USER:-appuser}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-appdb}
      REDIS_URL: redis://redis:6379
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      NEXTAUTH_URL: ${NEXTAUTH_URL:-http://localhost}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
    # No port mapping — accessed only via nginx proxy

  # ── Nginx Reverse Proxy ─────────────────────────────────────
  nginx:
    build:
      context: ./nginx
      dockerfile: Dockerfile
    container_name: app-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      app:
        condition: service_started
    networks:
      - backend

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  backend:
    driver: bridge
```

```nginx
# nginx/nginx.conf

worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    multi_accept on;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # ── Logging ────────────────────────────────────────────────
    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'rt=$request_time';

    access_log /var/log/nginx/access.log main;

    # ── Performance ────────────────────────────────────────────
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50m;

    # ── Gzip Compression ──────────────────────────────────────
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml
        application/xml+rss
        application/vnd.ms-fontobject
        application/x-font-ttf
        font/opentype
        image/svg+xml
        image/x-icon;

    # ── Rate Limiting ──────────────────────────────────────────
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    # ── Upstream ───────────────────────────────────────────────
    upstream app {
        server app:3000;
        keepalive 32;
    }

    # ── Redirect HTTP → HTTPS (uncomment when SSL configured) ─
    # server {
    #     listen 80;
    #     server_name _;
    #     return 301 https://$host$request_uri;
    # }

    # ── Server Block ──────────────────────────────────────────
    server {
        listen 80;
        server_name _;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:;" always;

        # ── Static assets (Next.js _next/static) ──────────────
        location /_next/static/ {
            proxy_pass http://app;
            proxy_cache_valid 200 365d;
            add_header Cache-Control "public, max-age=31536000, immutable";
        }

        # ── Public assets ─────────────────────────────────────
        location /public/ {
            proxy_pass http://app;
            add_header Cache-Control "public, max-age=86400";
        }

        # ── Health check endpoint ─────────────────────────────
        location /api/health {
            proxy_pass http://app;
            access_log off;
        }

        # ── Login rate limit ──────────────────────────────────
        location /api/auth/ {
            limit_req zone=login burst=3 nodelay;
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # ── API routes with rate limiting ─────────────────────
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }

        # ── Everything else → Next.js ─────────────────────────
        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
        }
    }
}
```

```dockerfile
# nginx/Dockerfile
FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/app.conf

RUN nginx -t

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```bash
# scripts/entrypoint.sh
#!/bin/sh
set -e

echo "[entrypoint] Waiting for PostgreSQL..."
until pg_isready -h postgres -p 5432 -U "${POSTGRES_USER:-appuser}" -q 2>/dev/null; do
    sleep 1
done
echo "[entrypoint] PostgreSQL is ready"

echo "[entrypoint] Running database migrations..."
# npx prisma migrate deploy
# npx drizzle-kit migrate

echo "[entrypoint] Starting application..."
exec node server.js
```

```env
# .env.example
POSTGRES_USER=appuser
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=appdb
DATABASE_URL=postgresql://appuser:CHANGE_ME_STRONG_PASSWORD@postgres:5432/appdb
REDIS_URL=redis://redis:6379
NEXTAUTH_SECRET=CHANGE_ME_GENERATE_WITH_openssl_rand_hex_32
NEXTAUTH_URL=http://localhost
NODE_ENV=production
```

## 4. Execution Protocol & Step-by-Step Workflow

```bash
# 1. Create project structure
mkdir -p scripts nginx

# 2. Copy all files into place
#    Dockerfile, .dockerignore, docker-compose.yml,
#    nginx/nginx.conf, nginx/Dockerfile,
#    scripts/entrypoint.sh, .env.example

# 3. Create .env from template (fill in real values)
cp .env.example .env
# Edit .env with actual secrets

# 4. Build the multi-stage image
docker compose build app --no-cache

# 5. Verify image size (should be <100MB)
docker images app-web
# Expected: ~80-95MB for the runner stage

# 6. Start the full stack
docker compose up -d

# 7. Verify all services are healthy
docker compose ps
# All three should show "healthy"

# 8. Check logs
docker compose logs -f app
docker compose logs -f postgres
docker compose logs -f nginx

# 9. Verify the application responds
curl -i http://localhost/api/health
# Expected: HTTP 200

# 10. Verify database connectivity
docker compose exec postgres psql -U appuser -d appdb -c "\dt"

# 11. Stop the stack
docker compose down

# 12. Stop and remove volumes (full reset)
docker compose down -v --remove-orphans
```

## 5. Edge Cases & Error Handling

- **Standalone output missing:** If `next.config.ts` does not include `output: "standalone"`, the final stage `COPY --from=builder /app/.next/standalone ./` will fail. Always verify with `npm run build` locally first.
- **Volume permission conflicts:** Named volumes persist data across `docker compose down`. Use `docker compose down -v` to reset, or `chown` the volume mount path if running non-root containers with bind mounts.
- **Build cache invalidation:** The `--no-cache` flag ensures a clean build. For iterative development, leverage Docker BuildKit cache mounts (`--mount=type=cache`) as shown in the npm ci layer.
- **PostgreSQL startup race:** The `depends_on: condition: service_healthy` ensures the app container waits for PostgreSQL to pass its health check before starting. Without this, the app will crash on first boot.
- **Nginx upstream DNS:** The `upstream app { server app:3000; }` relies on Docker Compose's internal DNS. The service name `app` must match exactly — Docker Compose resolves it automatically.
- **Image size bloat:** Running `npm ci` (including devDependencies) in the builder stage is fine because only the runner stage is published. To debug build issues, build with `--target builder` to inspect intermediate layers.
- **Redis memory limits:** The `--maxmemory 256mb --maxmemory-policy allkeys-lru` flags prevent Redis from consuming unbounded host memory. Adjust based on workload.
- **Rate limit bypass:** `limit_req_zone` uses `$binary_remote_addr`; if running behind another proxy (e.g., Cloudflare), add `$http_x_forwarded_for` or use a real IP module.
- **Entrypoint scripts:** Make sure `scripts/entrypoint.sh` has executable permissions (`chmod +x`) before building, or use `COPY --chmod=0755` with BuildKit.
- **Graceful shutdown:** Docker sends SIGTERM on `docker compose stop`; Next.js handles this natively. For custom cleanup (flush Redis writes, close DB connections), trap SIGTERM in the entrypoint script.

