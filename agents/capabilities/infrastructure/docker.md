# Docker — Best Practices

<!-- CAPABILITY REFERENCE
Fiche de best practices pour Docker (conteneurisation).
À combiner avec un rôle (ex: roles/engineering/platform-engineer.md).
-->

> **Version de référence :** Docker Engine 27.x / Docker Compose v2 | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [docs.docker.com](https://docs.docker.com/)

---

## 🏛️ Principes fondamentaux

### 1. Images minimales

```dockerfile
# ✅ Multi-stage build — image finale minimale
FROM php:8.3-fpm-alpine AS base
# ...dépendances runtime...

FROM base AS builder
COPY . /app
RUN composer install --no-dev --optimize-autoloader

FROM base AS production
COPY --from=builder /app /app
USER www-data
EXPOSE 9000
CMD ["php-fpm"]
```

| Image | Taille typique |
|---|---|
| `ubuntu:24.04` | ~78 MB |
| `alpine:3.19` | ~7 MB |
| `distroless/static` | ~2 MB |

**Règle :** Utilisez `alpine` ou `distroless` en production. Jamais `latest`.

### 2. Un processus par conteneur

```yaml
# ✅ Séparation des responsabilités
services:
  app:
    image: myapp:1.0
  db:
    image: mysql:8.0
  redis:
    image: redis:7-alpine
  nginx:
    image: nginx:alpine

# ❌ Tout dans un conteneur
# (Apache + PHP + MySQL + Redis dans la même image)
```

### 3. User non-root

```dockerfile
# ✅ Créer et utiliser un utilisateur non-root
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# ❌ Tourner en root (défaut)
# Pas de directive USER = root = danger
```

### 4. Tags explicites — jamais `latest`

```dockerfile
# ✅ Version explicite + digest pour la reproductibilité
FROM php:8.3.2-fpm-alpine3.19

# ❌ Imprévisible
FROM php:latest
FROM node
```

### 5. Layer caching — dépendances d'abord

```dockerfile
# ✅ Cache efficace — les dépendances changent rarement
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts

COPY . .
RUN composer dump-autoload --optimize

# ❌ Cache cassé à chaque changement de code
COPY . .
RUN composer install
```

---

## 📐 Patterns recommandés

### Dockerfile multi-stage

```dockerfile
# Stage 1: Dépendances
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

### Docker Compose — bonnes pratiques

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
# ✅ Toujours avoir un .dockerignore
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
# ❌ RUN multiples (→ layers inutiles)
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y git

# ✅ Un seul RUN + cleanup
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

# ❌ Secrets dans le Dockerfile
ENV DB_PASSWORD=mysecretpassword
COPY .env /app/.env

# ✅ Variables d'environnement au runtime ou Docker secrets
# docker run -e DB_PASSWORD_FILE=/run/secrets/db_pass

# ❌ COPY . . en premier
COPY . .
RUN npm install  # cache cassé à chaque changement

# ❌ Volumes en écriture sur des répertoires sensibles
# volumes: /:/host  # accès root au host
```

---

## 🔒 Sécurité

```
- [ ] Images scannées (Trivy, Snyk, docker scout)
- [ ] User non-root obligatoire
- [ ] Pas de secrets dans les images/layers
- [ ] Images signées (Docker Content Trust)
- [ ] Read-only filesystem quand possible
- [ ] Capabilities droppées (--cap-drop ALL + --cap-add nécessaires)
- [ ] Réseau isolé par service
```

---

## ✅ Checklist rapide

```
- [ ] Images minimales (alpine / distroless)
- [ ] Tags versionnés (jamais latest)
- [ ] Multi-stage builds
- [ ] Un processus par conteneur
- [ ] User non-root
- [ ] Layer caching optimisé (dépendances avant code)
- [ ] .dockerignore complet
- [ ] Healthchecks définis
- [ ] Secrets via env/secrets (jamais dans l'image)
- [ ] docker-compose avec depends_on + conditions
```
