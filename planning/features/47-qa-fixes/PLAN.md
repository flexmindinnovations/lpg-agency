# 47 — QA fixes — Plan

Fix the findings of the 2026-10-20 QA pass (report:
`/mnt/project-files/qa/qa-report-2026-10-20.md`, 114 findings) and the four
issues the product owner reported during it (Register Employee role list,
long page descriptions, Audit Log entity details), with a focus on UI/UX and
realtime notifications.

Work was split by area, each with its own notes file in this folder:
`inventory.md`, `auth.md`, `realtime.md`, `ui.md`, `billing.md`, `mobile.md`,
`orders.md`. Phone sign-in normalisation (CA-02) was done separately in PR #30.

Decisions: ADR-057 to ADR-063. GST pricing basis is exclusive by default
(product owner, 2026-10-21).
