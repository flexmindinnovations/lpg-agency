# 63 — Linked devices: delete a phone, and stop reinstalls looking like new phones

Goal: reinstalling the Admin or Driver app on the same phone no longer adds a row or asks for a name again, and an agency admin can delete a phone's record.

## What we found
- The server already keeps one record per phone per agency, matched by the hashed Android ID (ADR-072), and asks for a name only for a phone it has not seen.
- The production list shows the same phone (OnePlus OPD2514, Samsung SM-S938B) registered again after each install, each time with a different hardware reference, and each registration follows a run of the `Mobile test APKs` workflow by 15 to 25 minutes.
- Android scopes the Android ID by **app signing key** (Android reference, `Settings.Secure.ANDROID_ID`): it survives an uninstall and reinstall, but changes when the signing key changes. The workflow builds the APKs "debug-signed", and a fresh CI runner creates a new debug key every run, so every install from a new run looked like a new phone.

## Scope
1. **A stable signing key for test builds** of the Admin and Driver apps (and the Customer app, for consistency): one committed internal-test keystore, used by the CI workflow and as the local fallback when no release keystore is set up. Release (Play) builds are unchanged.
2. **Delete a phone** (agency admin, `license:manage_tenant`): `DELETE /admin/license/devices/{id}` removes the record for good. Its sessions end, the phone is told to re-check, the audit trail keeps a `device.deleted` entry. A phone that signs in again afterwards registers as new.
3. **Dashboard**: a Delete action on each row of the Linked Devices table, with a confirmation.

## Guardrails
- Only the agency's own phones can be deleted (tenant isolation, RLS plus an explicit check).
- Deleting an approved phone frees its seat and signs it out; the confirmation says so.
- The internal-test keystore protects nothing: its password is public. It must never be used for a Play upload (those use the upload key, `mobile/RELEASE.md`).

## Not in scope
- Recognising a phone whose Android ID changed (factory reset, new signing key). That is a new phone; the admin can delete the old record.
- Deleting from the mobile apps.
