# Tasks: Admin app editable profile

- [x] 1. `AuthApi.myProfile()` and `updateMyProfile()` plus the `MyProfile` model, with tests
- [x] 2. Admin Profile: "Edit profile" sheet (name, contact phone), contact phone shown on the screen, Sign Out full width
- [x] 3. Tests: validation, saving sends both fields, a refused save shows the server's reason, full-width Sign Out, and the name and phone read from the profile route
- [x] 4. Checked on the emulator against the local backend: saved a name and phone, saw both on the screen after a restart, then cleared them again
- [x] 5. Backend: `avatar_ref` on the staff user (Alembic migration `e4b7a1c9d3f2`), domain `set_avatar` / `clear_avatar`, use cases `SetMyAvatarUseCase` / `RemoveMyAvatarUseCase`, audit
- [x] 6. Backend: `POST` / `DELETE /auth/me/avatar` (JPEG, PNG, WebP or HEIC, 5 MB, type checked against the file's own bytes, tenant-scoped key); profile responses carry `avatar_url`; OpenAPI spec regenerated and committed
- [x] 7. Backend tests: unit (domain rules, refusals, replace deletes the old object, failed save cleans up), integration against PostgreSQL (keep / replace / remove, tenant isolation), and a real-stack HTTP round trip against MinIO
- [x] 8. `LpgAvatar` gains an optional `imageUrl` (initials stay while loading or if the link fails); `AuthApi.setMyAvatar` / `removeMyAvatar`; Admin Profile avatar opens Take photo / Choose from gallery / Remove photo; tests for each
- [x] 9. Checked on the emulator against the local backend: picked a picture from the gallery, saw it in the circle, removed it, confirmed the database column and the stored object were gone
- [ ] 10. Follow-up chore: regenerate the dashboard's API client (`npm run generate:api-client` in `frontend/`). It is already behind the committed spec for unrelated routes (order settlement, a proof-of-delivery field), so a regeneration belongs in its own change, not in this one; the dashboard does not use the picture yet
- [ ] 11. Not done: pictures for Driver and Customer apps (out of scope, see PLAN); showing the admin's own picture anywhere other than the Profile screen (nothing else in the Admin app shows it today)
