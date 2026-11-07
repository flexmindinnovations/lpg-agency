# 62 — Admin app: editable profile

Goal: the signed-in agency admin can change their own details and picture from the Admin app's Profile screen.

## What already exists
- Backend `GET` / `PATCH /api/v1/auth/me/profile` (DA-30): own name (max 120) and contact phone (digits, spaces, dashes, optional leading `+`, 7 to 20 characters). The PATCH replaces both values (a blank clears), is audited, and never touches the sign-in email. The web dashboard already uses it.
- `POST /api/v1/documents/attachments` stages a tenant-scoped image and returns a blob ref.

## Scope, in order
1. **Name and phone from the Admin app** (mobile only; no backend change). A sheet on the Profile screen; the email stays read-only. Sign-out button full width.
2. **Profile picture** (needs the backend): an `avatar_ref` on the staff user (migration), a use case that sets or clears it, `POST /auth/me/avatar` (image only, size limit, tenant-scoped key), the profile response carrying a displayable URL, tests including tenant isolation and an audit entry. In the app: pick from camera or gallery, upload, show it in `LpgAvatar` (new optional image) on the Profile card and anywhere else the user's avatar is shown.

## Guardrails
- The email is the sign-in identifier and is not editable here.
- No picture is ever shown across tenants (tenant-scoped storage key, URL only for the owner's tenant).
- Every change is audited (already true for name and phone).

## Not in scope
- Changing the email or password from the app (password change exists in the API; separate story).
- Pictures for Driver and Customer apps.
