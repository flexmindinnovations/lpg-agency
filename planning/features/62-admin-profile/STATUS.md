# Status: Admin app editable profile

**Built and checked on a device**, in two parts: name, phone and full-width Sign Out (PR #153), and the profile picture (this branch, stacked on #153).

## Done (2026-11-06)
- Name and phone: `AuthApi.myProfile()` / `updateMyProfile()`, an "Edit profile" sheet, the contact phone shown once set, Sign Out full width.
- Profile picture, backend:
  - `identity.identity_user.avatar_ref` (nullable, migration `e4b7a1c9d3f2`). It holds the storage key, never a URL.
  - `POST /auth/me/avatar` (multipart `file`) and `DELETE /auth/me/avatar`. A picture must be JPEG, PNG, WebP or HEIC, at most 5 MB, and its first bytes must match the type it claims; anything else is a 422 and nothing is stored.
  - Stored at `tenant/{tenant_id}/avatars/{user_id}/{random}.{ext}`. A new name each time, the old object is deleted, and a failed save removes the new upload.
  - `GET` / `PATCH /auth/me/profile` and the two new routes return `avatar_url`, a link that expires after an hour and is made on every read.
  - Each change is audited (`own_avatar`, `set` or `removed`) without the key.
  - OpenAPI spec regenerated (additions only).
- Profile picture, app:
  - `LpgAvatar(imageUrl:)`: the picture fades in over the initials; while loading, or if the link fails or has expired, the initials stay.
  - Admin Profile: the avatar has a camera badge; tapping it offers Take photo, Choose from gallery and (when there is one) Remove photo. A chosen photo is shrunk to at most 1024 px before it is sent; the type is read from the file's bytes.

## Verified
- Backend: `ruff check` and `ruff format`, `mypy --strict`, `import-linter` (7 contracts kept), 1,686 unit tests pass. The new integration tests (keep / replace / remove, another agency cannot reach the picture, HTTP round trip through MinIO including fetching the link and seeing it stop working after removal) pass against a freshly migrated PostgreSQL database.
- App: format, analyze and tests in `design_system`, `api_client`, `admin_app`, `customer_app` and `driver_app` (see the PR for counts).
- Emulator (Pixel 10 Pro, local backend and MinIO): picked a picture from the gallery, saw it in the profile circle, removed it and saw the initials and "Profile picture removed."; the database column and the stored object were gone afterwards. The dev account is back as it was.

## Not verified
- Taking a photo with the camera on a device (the gallery path was run; the camera path is covered by a widget test with a fake picker).
- A refused upload (422) on a device; covered by a widget test and an HTTP integration test.
- The expired-link case on a device: after about an hour the link stops working and the initials show until the profile is read again. Covered by a widget test only.
- The full integration suite: the shared `lpg_test` database on this machine is at a migration from another branch, so the profile tests were run against a fresh database built from this branch's migrations. CI builds its own.

## Notes
- The link points at the storage endpoint. In local development that is `localhost:59000`, so an emulator needs `adb reverse tcp:59000 tcp:59000` to show the picture; a deployed environment needs a storage endpoint the phones can reach (the same need as the existing invoice and KYC links).
- Dozens of integration test files hard-code the `lpg_test` database name and ignore `LPG_TEST_ADMIN_DATABASE_URL`. Left alone; worth one tidy-up task.

## Decision (was open)
Pictures use the existing object storage under the user's own `tenant/{id}/avatars/` prefix, served by a short-lived signed link (same approach as invoices and KYC documents). No new storage service.
