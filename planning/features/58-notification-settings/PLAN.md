# 58 — Notification settings per event (ADR-068)

Goal: agency admins choose, per system event, which channels fire (in-app, push, SMS, email), from the web dashboard. Applies to the customer app, driver app, admin app and the dashboard bell, because they all receive what the backend sends.

## Scope
- `notification.notification_preference` (nullable channel overrides per tenant and type; NULL = catalogue default).
- `application/notification/preferences.py` (rules), `infrastructure/notification/event_catalog.py` (description, group, critical flag per catalogue type), repository, `/notification-settings` API.
- `NotificationResolver` applies overrides; `delivery.py` and the `send_notification` job honour the in-app/push/SMS/email flags.
- Dashboard: Settings > Notifications.

## Guardrails
- Critical events cannot lose their in-app alert (API 422).
- SMS only where a DLT template exists, email only where the catalogue has one.
- Delivery OTP / login OTP are outside the catalogue and unaffected.

## Not in scope
- Per-event recipient roles: recipients stay RBAC-driven (permission on the catalogue spec).
- Per-user mute preferences in the apps.
- Quiet hours.

## Tests
- Unit: `tests/unit/test_notification_preferences.py`.
- Integration (PostgreSQL): `tests/integration/test_notification_settings_smoke.py`.
- Dashboard: `settings/notifications/notification-settings.spec.ts`.
