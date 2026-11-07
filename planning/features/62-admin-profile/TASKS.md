# Tasks: Admin app editable profile

- [x] 1. `AuthApi.myProfile()` and `updateMyProfile()` plus the `MyProfile` model, with tests
- [x] 2. Admin Profile: "Edit profile" sheet (name, contact phone), contact phone shown on the screen, Sign Out full width
- [x] 3. Tests: validation, saving sends both fields, a refused save shows the server's reason, full-width Sign Out, and the name and phone read from the profile route
- [x] 4. Checked on the emulator against the local backend: saved a name and phone, saw both on the screen after a restart, then cleared them again
- [ ] 5. Backend: `avatar_ref` on the staff user (Alembic migration), domain method, use case, audit
- [ ] 6. Backend: `POST` / `DELETE /auth/me/avatar` (image only, size limit, tenant-scoped key); profile response carries `avatar_url`; OpenAPI spec regenerated and committed
- [ ] 7. Backend tests: unit, integration, tenant isolation
- [ ] 8. `LpgAvatar` gains an optional image; Admin app picks, uploads and shows the picture
- [ ] 9. Update `knowledge/12-current-status.md` and `planning/current_phase.md` when the picture ships
