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

## Push notifications setup (Firebase) — from scratch

The app uses Firebase Cloud Messaging (FCM). The code is already wired
(`lib/src/push/push_notification_service.dart`, backend
`infrastructure/channels/push_channel.py`); this section is the one-time
environment setup. **Until step 2 is done the Android build fails** — the
`com.google.gms.google-services` Gradle plugin errors on a missing
`google-services.json`.

Identifiers you'll need:

| | value |
|---|---|
| Android package name | `com.lpgagency.customer_app` |
| iOS bundle id | `com.lpgagency.customerApp` |
| Firebase config → Android | `android/app/google-services.json` |
| Firebase config → iOS | `ios/Runner/GoogleService-Info.plist` |

All three generated files (`google-services.json`,
`GoogleService-Info.plist`, `lib/firebase_options.dart`) are gitignored —
per-project, added out of band.

### 1. Create the Firebase project

1. <https://console.firebase.google.com> → **Add project**. Name it
   (e.g. `lpg-agency`), Google Analytics optional.
2. Once created, note the **Project ID** (Project settings → General) —
   the backend needs it.

### 2. Android app

**Option A — FlutterFire CLI (does Android + iOS at once):**

```bash
dart pub global activate flutterfire_cli
cd mobile/apps/customer_app
flutterfire configure --project=<your-project-id>
```

Pick the Android + iOS platforms when prompted. This writes
`android/app/google-services.json`, `ios/Runner/GoogleService-Info.plist`,
and `lib/firebase_options.dart`. Then skip to step 4.

**Option B — Firebase console, by hand:**

1. Console → Project overview → **Add app** → Android.
2. Package name: `com.lpgagency.customer_app`. Nickname/SHA-1 optional
   (SHA-1 only needed for Dynamic Links / phone auth, not FCM).
3. **Download `google-services.json`** → place at
   `mobile/apps/customer_app/android/app/google-services.json`.
4. Skip the "add SDK" gradle snippets — this repo already has the
   `com.google.gms.google-services` plugin in `android/settings.gradle.kts`
   and `android/app/build.gradle.kts`.

Then bump the Android `minSdk` — `firebase_core` 3.x needs API 23+. In
`android/app/build.gradle.kts`, change `minSdk = flutter.minSdkVersion` to:

```kotlin
minSdk = maxOf(flutter.minSdkVersion, 23)
```

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

1. Firebase console → Project settings → **Service accounts** → **Generate
   new private key**. Downloads a JSON file.
2. Give its **entire contents** to the backend as a single-line env var:

   ```bash
   # backend/.env
   LPG_FCM_CREDENTIALS_JSON={"type":"service_account","project_id":"lpg-agency",...}
   LPG_FCM_PROJECT_ID=lpg-agency   # optional; read from the JSON otherwise
   ```

   Without this the backend runs `StubPushChannel` — logs each push, sends
   nothing. Restart the ARQ worker after setting it.
3. Apply the device-token migration:

   ```bash
   cd backend && uv run alembic upgrade head   # brings in f3a9c1e07b42
   ```

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
