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

## Push notifications setup (Firebase)

The app uses Firebase Cloud Messaging (FCM), wired to a dev Firebase
project **`lpg-erp-2b143`**. Its client config *is committed* —
`android/app/google-services.json`, `lib/firebase_options.dart`,
`firebase.json` — so a fresh clone builds and runs on Android with no extra
setup. These aren't secrets (Firebase enforces access server-side); for a
separate prod project, swap them in CI.

Verified working 2026-08-31: launch → permission prompt → FCM token →
`POST /notifications/devices` → row in `notification.device_token`.

What's *not* committed / still needed:

| item | why |
|---|---|
| `ios/Runner/GoogleService-Info.plist` | iOS not set up yet — run `flutterfire configure` again with `ios` when needed, plus an APNs key |
| `LPG_FCM_CREDENTIALS_JSON` (backend) | without it the backend uses `StubPushChannel` (logs, sends nothing) — see step 2 |

### 1. (Only for a NEW Firebase project) regenerate the client config

Skip unless you're moving off `lpg-erp-2b143`.

```bash
firebase login
cd mobile/apps/customer_app
flutterfire configure --project=<project-id> --platforms=android,ios --yes
```

Identifiers: Android package `com.lpgagency.customer_app`, iOS bundle
`com.lpgagency.customerApp`. The `com.google.gms.google-services` Gradle
plugin, `minSdk = maxOf(flutter.minSdkVersion, 23)`, and core-library
desugaring are already in `android/app/build.gradle.kts`.

### 3. iOS app (skip if not shipping iOS yet)

1. Console → Add app → iOS. Bundle id: `com.lpgagency.customerApp`.
2. Download **`GoogleService-Info.plist`** → `ios/Runner/`, and in Xcode
   drag it into the **Runner** target (check "Copy items if needed").
3. Apple Push requires a paid Apple Developer account: create an **APNs
   auth key** (`.p8`) at developer.apple.com → Keys, then upload it in
   Firebase → Project settings → Cloud Messaging → Apple app configuration.
4. In Xcode, Runner target → Signing & Capabilities → **+ Capability** →
   Push Notifications, and Background Modes → Remote notifications.

### 4. Backend — service account key

1. [Firebase console](https://console.firebase.google.com/project/lpg-erp-2b143/settings/serviceaccounts/adminsdk)
   → Project settings → **Service accounts** → **Generate new private key**.
   Downloads a JSON file.
2. Give its **entire contents** to the backend as a single-line env var:

   ```bash
   # backend/.env
   LPG_FCM_CREDENTIALS_JSON={"type":"service_account","project_id":"lpg-erp-2b143",...}
   LPG_FCM_PROJECT_ID=lpg-erp-2b143   # optional; read from the JSON otherwise
   ```

   Without this the backend runs `StubPushChannel` — logs each push, sends
   nothing. Restart the ARQ worker after setting it.
3. The device-token migration (`f3a9c1e07b42`) is already applied to local
   dev. For a fresh DB: `cd backend && uv run alembic upgrade head`.

### 5. Verify end to end

```bash
cd mobile/apps/customer_app
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

- On launch you should get the notification-permission prompt; grant it.
- Log in. The app calls `POST /api/v1/notifications/devices` — check the
  row lands: `SELECT platform, left(token, 12) FROM notification.device_token;`
- Trigger a customer-facing event (place an order → `booking_confirmed`).
  The ARQ worker's `send_notification` job logs a `channel='push'` row in
  `notification.notification_log`; with real credentials the device shows a
  tray notification. Tapping it deep-links via `data.reference_type` /
  `data.reference_id` (order → order detail, invoice → invoice detail).
- Foreground messages are rendered by `flutter_local_notifications` on the
  `lpg_default_channel` channel.

### Production notes

- `google-services.json` / `GoogleService-Info.plist` are **not secrets**
  (they're shipped in the app binary) but are environment-specific — inject
  them in CI rather than committing.
- `LPG_FCM_CREDENTIALS_JSON` **is** a secret — it can send push to every
  user. Store it in the deployment secret manager, never in the repo.
- Use separate Firebase projects (or at least separate Android/iOS app
  registrations) per environment if you want prod/UAT push isolation.
