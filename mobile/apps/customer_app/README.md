# customer_app

The LPG Agency customer-facing Flutter app.

## Running against the local backend

Bring up the backend stack (`scripts/dev-up.sh` — Postgres, Redis, MinIO on
non-default ports) and run the API (`.claude/backend-dev.bat` or
`uvicorn`), then:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the Android emulator's alias for the host machine; the app
defaults to `http://localhost:8000` for desktop/web runs where that
resolves directly. A real device needs the host's LAN IP instead.

### Presigned storage URLs on the emulator

KYC document photos (and other stored files) are returned as short-lived
presigned URLs pointing at the backend's storage endpoint, which in local
dev is MinIO on `http://localhost:59000`. The emulator can't reach the
host's `localhost`, so those image loads fail (the UI degrades to a
placeholder icon) unless you forward the port into the emulator:

```bash
adb reverse tcp:59000 tcp:59000
```

Re-run that after an emulator cold boot or `adb kill-server`. Production
uses a real S3-compatible endpoint reachable from anywhere, so this step
is local-only.
