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

The app uses Firebase Cloud Messaging. **The Android build fails until the
Firebase config files are in place** — the `com.google.gms.google-services`
Gradle plugin errors on a missing `google-services.json`.

One-time setup:

1. Create a Firebase project (or reuse one) at <https://console.firebase.google.com>.
2. Add an **Android app** with package name `com.lpgagency.customer_app`.
   Download `google-services.json` into
   `android/app/google-services.json`.
3. Add an **iOS app** with bundle id `com.lpgagency.customerApp` (check
   `ios/Runner.xcodeproj`). Download `GoogleService-Info.plist` into
   `ios/Runner/` and add it to the Runner target in Xcode.
4. In the Firebase console → Project settings → Cloud Messaging, generate a
   **service-account private key** (Project settings → Service accounts →
   Generate new private key). Give its JSON contents to the backend as
   `LPG_FCM_CREDENTIALS_JSON` (single line). Without this the backend logs
   pushes but sends nothing (`StubPushChannel`).

Both config files are gitignored — they're per-project, not secrets to
share in the repo. `flutterfire configure` automates steps 2–3 if you have
the FlutterFire CLI.

The client registers its FCM token with `POST /notifications/devices` on
every launch once authenticated, and drops it on logout. Notification taps
deep-link via `data.reference_type` / `data.reference_id` (order → order
detail, invoice → invoice detail).
