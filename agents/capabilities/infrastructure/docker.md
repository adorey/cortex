# Docker — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for Docker (containerisation).
To combine with a role (e.g. roles/engineering/platform-engineer.md).
-->

> **Reference version:** Docker Engine 27.x / Docker Compose v2 | **Last updated:** 2026-02
> **Official docs:** [docs.docker.com](https://docs.docker.com/)

---

## 🏛️ Fundamental principles

### 1. Minimal images

```dockerfile
# ✅ Multi-stage build — minimal final image
FROM php:8.3-fpm-alpine AS base
# ...runtime dependencies...

FROM base AS builder
COPY . /app
RUN composer install --no-dev --optimize-autoloader

FROM base AS production
COPY --from=builder /app /app
USER www-data
EXPOSE 9000
CMD ["php-fpm"]
```

| Image | Typical size |
|---|---|
| `ubuntu:24.04` | ~78 MB |
| `alpine:3.19` | ~7 MB |
| `distroless/static` | ~2 MB |

**Rule:** Use `alpine` or `distroless` in production. Never `latest`.

### 2. One process per container

```yaml
# ✅ Separation of concerns
services:
  app:
    image: myapp:1.0
  db:
    image: mysql:8.0
  redis:
    image: redis:7-alpine
  nginx:
    image: nginx:alpine

# ❌ Everything in one container
# (Apache + PHP + MySQL + Redis in the same image)
```

### 3. Non-root user

```dockerfile
# ✅ Create and use a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# ❌ Running as root (default)
# No USER directive = root = dangerous
```

### 4. Explicit tags — never `latest`

```dockerfile
# ✅ Explicit version + digest for reproducibility
FROM php:8.3.2-fpm-alpine3.19

# ❌ Unpredictable
FROM php:latest
FROM node
```

### 5. Layer caching — dependencies first

```dockerfile
# ✅ Efficient cache — dependencies rarely change
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts

COPY . .
RUN composer dump-autoload --optimize

# ❌ Cache busted on every code change
COPY . .
RUN composer install
```

---

## 📐 Recommended patterns

### Multi-stage Dockerfile

```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production

# Stage 2: Build
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: Production
FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist ./dist
COPY --from=deps /app/node_modules ./node_modules
USER node
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

### Docker Compose — best practices

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      target: production
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: mysql:8.0.36
    volumes:
      - db_data:/var/lib/mysql
    environment:
      MYSQL_ROOT_PASSWORD_FILE: /run/secrets/db_root_password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  db_data:
    driver: local
```

### .dockerignore

```
# ✅ Always include a .dockerignore
.git
.env
.env.local
node_modules
vendor
docker-compose*.yml
*.md
tests/
.github/
```

### Healthchecks

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

---

## 🚫 Anti-patterns

```dockerfile
# ❌ Multiple RUN statements (→ unnecessary layers)
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y git

# ✅ Single RUN + cleanup
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

# ❌ Secrets in the Dockerfile
ENV DB_PASSWORD=mysecretpassword
COPY .env /app/.env

# ✅ Environment variables at runtime or Docker secrets
# docker run -e DB_PASSWORD_FILE=/run/secrets/db_pass

# ❌ COPY . . first
COPY . .
RUN npm install  # cache busted on every change

# ❌ Write volumes on sensitive directories
# volumes: /:/host  # root access to the host
```

---

## 🔒 Security

```
- [ ] Images scanned (Trivy, Snyk, docker scout)
- [ ] Non-root user mandatory
- [ ] No secrets in images/layers
- [ ] Signed images (Docker Content Trust)
- [ ] Read-only filesystem where possible
- [ ] Dropped capabilities (--cap-drop ALL + --cap-add as needed)
- [ ] Network isolated per service
```

---

## ✅ Quick checklist

```
- [ ] Minimal images (alpine / distroless)
- [ ] Versioned tags (never latest)
- [ ] Multi-stage builds
- [ ] One process per container
- [ ] Non-root user
- [ ] Optimised layer caching (dependencies before code)
- [ ] Complete .dockerignore
- [ ] Healthchecks defined
- [ ] Secrets via env/secrets (never baked into the image)
- [ ] docker-compose with depends_on + conditions
```
