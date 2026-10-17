# 38 — Production release setup — Status

**2026-10-17 — In review.** Deploy and release-build setup done; not yet verified
end to end because no Flutter SDK or signing key was available in the authoring
environment (`docker compose config` verified the compose change, including that
commented-out lines in `integrations.env` stay unset). The Android signing change and
`mobile-release.yml` get their first real run once the owner adds the keystore secrets.

Nothing has been changed on the production server by this work.
