# 48 — Admin App order flow — Tasks

- [x] Order page actions and progress (confirm, send out, deliver, fail, reschedule, close, cancel review)
- [x] Send out sheet on `load-and-dispatch`
- [x] Orders list filters on real statuses
- [x] Live updates and Alerts tab over `/ws`
- [x] Sentence-case status chips (all apps)
- [x] admin_app in Mobile CI
- [x] FCM push for the Admin App (PR #68; google-services.json for com.lpgagency.admin_app is in place)
- [x] Load-out weighment from the app (Send out sheet asks for it on `WEIGHMENT_CHECK_REQUIRED`)
- [x] New order form matches the dashboard: customer search, address, booking source, delivery day, several lines from `orderable-cylinder-types` with stock, server-matching validation, retry-safe idempotency key
- [x] Orders list: server search, single-status filters answered by the server, "Load more" paging
- [x] Record delivery: optional OMC code, refuses a hand-over of zero cylinders
- [x] Dispatch tab (waiting orders with Send out, active trips with stops)
- [ ] Optional delivery photo/signature from the app
- [ ] Untested on a real device: push (foreground/background/tap), weighment flow against a gated agency
