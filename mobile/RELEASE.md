# Releasing the Customer and Driver apps

| App | Android application ID | iOS bundle ID |
|---|---|---|
| Customer | `com.lpgagency.customer_app` | `com.lpgagency.customerApp` |
| Driver | `com.lpgagency.driver_app` | `com.lpgagency.driverApp` |

**Confirm both IDs before the first store upload.** Once an app is published
under an ID it can never change; renaming later means a new store listing.

Both apps talk to the backend at `API_BASE_URL`, which defaults to
`https://lpg.vitessetec.com` and can be overridden per build with
`--dart-define=API_BASE_URL=...`.

> **Sign-in needs real SMS.** Release builds hide the dev OTP banner, so
> customers and drivers can only sign in once the backend sends OTPs by SMS
> (`LPG_SMS_PROVIDER=msg91` with the login OTP template — see
> `infrastructure/deploy/integrations.env.example`).

## Android

### 1. Create the upload key (once)

One upload key can sign both apps. Keep the file and its passwords somewhere
safe and off the repository; losing it means asking Google to reset it.

```bash
keytool -genkey -v -keystore upload-keystore.jks -storetype JKS \
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Enrol both apps in **Play App Signing** when creating them in the Play
Console (the default), so Google holds the real signing key and this file is
only the upload key.

### 2. Build in CI (recommended)

Add these to GitHub -> repository Settings -> Environments -> `production`:

| Name | Kind | Value |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | secret | `base64 -w0 upload-keystore.jks` (PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("upload-keystore.jks"))`) |
| `ANDROID_KEYSTORE_PASSWORD` | secret | keystore password |
| `ANDROID_KEY_ALIAS` | secret | `upload` (or the alias you chose) |
| `ANDROID_KEY_PASSWORD` | secret | key password |
| `LOCATIONIQ_API_KEY` | secret | LocationIQ key for maps and address search |
| `MOBILE_API_BASE_URL` | variable | optional; defaults to `https://lpg.vitessetec.com` |

Then Actions -> **Mobile release** -> Run workflow (or push a `mobile-v*`
tag). Each run produces `customer_app-release-aab` and
`driver_app-release-aab` artifacts. The build number is the run number; the
version name is `version:` in each app's `pubspec.yaml`.

### 3. Build locally (alternative)

Create `android/key.properties` in the app (git-ignored) and put the keystore
in `android/app/`:

```properties
storeFile=upload-keystore.jks
storePassword=...
keyAlias=upload
keyPassword=...
```

```bash
flutter build appbundle --release --dart-define-from-file=dart_defines.local.json
```

Without `key.properties` a release build is signed with the debug key, which
the Play Console rejects.

### 4. Upload

The first upload of each app is manual: Play Console -> Create app -> Testing
-> Internal testing -> upload the `.aab`. Fill in the store listing, content
rating, data-safety form and privacy policy URL before promoting to
production.

## iOS

iOS builds need a Mac with Xcode (or a macOS CI runner) and an Apple
Developer Program membership. Not automated yet; per app:

1. Register the bundle ID and create the app in App Store Connect.
2. Add `ios/Runner/GoogleService-Info.plist` from the Firebase project (push
   notifications) and enable the Push Notifications capability with an APNs
   key uploaded to Firebase.
3. In Xcode, set the team under Signing & Capabilities, then
   `flutter build ipa --release --dart-define=API_BASE_URL=https://lpg.vitessetec.com`
   and upload with Transporter or Xcode Organizer.
