# Status: Admin app editable profile

**In progress.** Step 1 (name and phone, full-width Sign Out) is built, tested and checked on the emulator. The picture (steps 5 to 8) is not started: it needs a backend change.

## Done (2026-11-06)
- `AuthApi.myProfile()` and `updateMyProfile()` in `api_client`, with tests (read, PATCH of both fields, a refused save).
- Admin Profile screen: an "Edit profile" button opens a sheet with name and contact phone (same phone rule as the server, checked before sending); the contact phone shows on the screen once set; Sign Out is full width.
- Widget tests in `admin_app/test/profile_test.dart`: validation, saving sends both fields trimmed, a bad phone sends nothing, the server's reason shows when a save is refused, Edit button present and Sign Out spans the page.
- `flutter analyze` clean and tests pass in `api_client` (142), `admin_app` (132), `design_system`, `customer_app`, `driver_app`.

## Verified on the emulator (Pixel 10 Pro, local backend)
Edit profile sheet opens; with the keyboard up, Save changes stays pinned above it; a real save of a name and phone showed "Profile updated.", the phone on the screen, and after a restart the name "Asha Rao" with AR initials on the card. The values were then cleared again, so the dev account is back as it was.

## Found while checking
`GET /auth/me` can return a stale name right after an edit, so the app now reads the name and phone from `GET /auth/me/profile` (a test covers it). Not investigated on the backend: why `/auth/me` lags.

## Not verified
- A refused save (the server's 422) on a device; it is covered by a widget test only.
- Anywhere else the app might show the principal's name (none found in the Admin app).

## Open decision
- Where profile pictures are stored and served (the existing staged-document storage, with a URL for the owner's tenant only) is proposed in PLAN.md; confirm before building steps 5 to 8.
