# Internal test signing key

`internal-test.keystore` signs the **test APKs** (CI "Mobile test APKs" and local
`flutter build apk --release`) for the Customer, Driver and Admin apps whenever
no real release key (`android/key.properties`, see `../RELEASE.md`) is present.

| | |
|---|---|
| Store / key password | `lpg-internal-test` |
| Alias | `lpg-internal-test` |

**Why it is committed.** Android derives a phone's ID (`ANDROID_ID`) from the app's
signing key. With the default per-machine debug key, every CI run signed with a
brand-new key, so each freshly downloaded APK looked like a different phone: the
apps asked for the phone's name again and a new row appeared in Linked Devices
(ADR-073). One shared key keeps a phone's identity across builds and reinstalls.

**Never use it for the Play Store or anything customers install.** The password is
public by design; anyone who has it can sign an app that installs over a test
build. Real releases use the upload key described in `../RELEASE.md`.

Switching an already-installed test app from the old debug-signed build to this
key needs a **one-time uninstall** (Android refuses an update signed differently).
