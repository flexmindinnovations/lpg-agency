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
# --legacy-peer-deps: @ngrx/signals@21 declares an Angular 21 peer range while
# the workspace is on Angular 22, so plain `npm ci` fails with ERESOLVE.
RUN --mount=type=cache,target=/root/.npm npm ci --legacy-peer-deps

COPY . .
# app.config.ts imports the git-ignored ./prime-license (a local-only licence
# key). A fresh clone lacks it, so fall back to the committed template, which
# builds PrimeNG unlicensed. Replace with a real key to remove PrimeNG's banner.
RUN cp -n apps/dashboard/src/app/prime-license.example.ts apps/dashboard/src/app/prime-license.ts
RUN npx nx build dashboard

FROM caddy:2-alpine
COPY --from=build /app/dist/apps/dashboard/browser /srv
COPY Caddyfile /etc/caddy/Caddyfile
