---
id: dockerfile-builder
name: dockerfile-builder
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: dockerfile-builder
file_path: skills/dockerfile-builder.md
name: Dockerfile Builder
category: devops
tags: [docker, multi-stage-build, container-security, image-optimization]
author: opencode-core
version: 1.0.0
description: Draft efficient, secure, and minimal multi-stage Dockerfiles.
---

# Dockerfile Builder

## Prerequisites & Dependencies
- Docker Engine 20.10+ (Docker Desktop or Podman with BuildKit enabled)
- Project source with a dependency manifest (`package.json`, `requirements.txt`, `go.mod`, `pom.xml`, ...)
- No API keys required; a `.dockerignore` must exist so secrets (`.env`, key files) never enter image layers

## Execution Steps
1. Choose slim, version-pinned base images: a toolchain image for the build stage, a minimal runtime base (`*-alpine`, `distroless`, or `*-slim`).
2. Structure the file as multi-stage: compile/install in a `build` stage, copy only produced artifacts into the `runtime` stage.
3. Order layers for cache efficiency: copy dependency manifests first, install dependencies, then copy source last.
4. Harden security: run as a non-root user (`USER`), never bake secrets via `ARG`, and clean package caches (`--no-cache`, `rm -rf /var/lib/apt/lists/*`).
5. Add `HEALTHCHECK`, required `EXPOSE`/`ENV` declarations, and an exec-form `ENTRYPOINT`/`CMD`.
6. Build, inspect layer history and image size, then scan for CVEs; iterate until size and vulnerability profile are acceptable.

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY src ./src
RUN npm run build && npm prune --omit=dev

FROM gcr.io/distroless/nodejs20-debian12:nonroot AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
USER nonroot
HEALTHCHECK CMD ["node", "-e", "fetch('http://localhost:3000/health')"]
```

```bash
DOCKER_BUILDKIT=1 docker build -t app:local .
docker history app:local --no-trunc
docker scout cves app:local
```
