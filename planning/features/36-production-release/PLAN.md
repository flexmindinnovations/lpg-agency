# 36 — Production release setup

## Goal

Make the merged feature set (SMS #11, Razorpay #12, WhatsApp AI #13, mobile UI #14)
deployable and the Customer/Driver apps releasable to the stores.

## Context

The backend and dashboard already deploy automatically: merge to `main` ->
`.github/workflows/deploy.yml` -> GHCR -> DigitalOcean droplet
(`https://lpg.vitessetec.com`, `infrastructure/deploy/DEPLOY.md`). Missing pieces:

1. The production compose file passes none of the new integration settings
   (MSG91, Razorpay, WhatsApp Cloud API, Anthropic, FCM).
2. Both Android apps sign release builds with the debug key.
3. There is no workflow that produces store-ready mobile builds.

## Design

- Integration credentials go in a separate, optional, git-ignored
  `infrastructure/deploy/integrations.env`, loaded with `env_file` by backend and
  worker only. A separate file keeps the Postgres admin password in `.env` out of
  the app containers, and lets unused settings stay truly unset: several of them
  are `SecretStr | None` and treat an empty string differently from `None`
  (an empty WhatsApp app secret would make signature checks meaningless), so a
  `${VAR:-}` passthrough in `environment:` is not safe.
- Android: standard Flutter `key.properties` signing, debug-key fallback when absent.
- `.github/workflows/mobile-release.yml`: manual / `mobile-v*` tag, builds signed
  AABs for both apps on the `production` environment's secrets, uploads artifacts.
- iOS stays manual (needs a Mac and an Apple Developer account) — documented in
  `mobile/RELEASE.md`.
