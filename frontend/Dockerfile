# syntax=docker/dockerfile:1

# Builds the Nx Angular dashboard and serves it with Caddy, which also
# reverse-proxies /api and /health to the backend (see Caddyfile).

FROM node:24-slim AS build
WORKDIR /app

ENV NX_DAEMON=false \
    CI=true \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NODE_OPTIONS=--max-old-space-size=1536

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
RUN npx nx build dashboard

FROM caddy:2-alpine
COPY --from=build /app/dist/apps/dashboard/browser /srv
COPY Caddyfile /etc/caddy/Caddyfile
