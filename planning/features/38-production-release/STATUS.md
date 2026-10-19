# 38 — Production release setup — Status

**2026-10-17 — In review.** Deploy and release-build setup done; not yet verified
end to end because no Flutter SDK or signing key was available in the authoring
environment (`docker compose config` verified the compose change, including that
commented-out lines in `integrations.env` stay unset). The Android signing change and
`mobile-release.yml` get their first real run once the owner adds the keystore secrets.

Nothing has been changed on the production server by this work.

**2026-10-19 — Push notifications.** Mobile push was not arriving; the likely cause is that the
production worker had no Firebase service account and fell back to the stub
channel. The deploy now takes an optional `FCM_SERVICE_ACCOUNT_JSON` GitHub
environment secret, writes it into `integrations.env` on the server, and reports
`push: FCM enabled` (or why not) at the end of the deploy log. Verified locally:
the env-file update is idempotent, rejects non-service-account input, and
`docker compose config` keeps the single-quoted JSON literal.
