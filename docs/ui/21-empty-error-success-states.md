# 21 — Empty, Error, and Success States

## Purpose
Designs Empty States, Offline States, No Data, Permission Denied, Error Pages, Success Screens, and Maintenance Screens — the platform's full set of non-happy-path UX patterns.

## 1. Empty States
Applies to any List/Grid screen with zero records (`07-wireframe-specifications.md` Template A). Structure: centered illustration (`08-design-system.md` illustration set) plus a one-sentence explanation plus a primary CTA where a meaningful next action exists.

| Screen Context | Message | CTA |
|---|---|---|
| Order Queue, no orders | "No orders yet for this filter" | Create Order (if permitted) or Clear filters |
| Customer List, no customers | "No customers registered yet" | Add Customer |
| Complaint Queue, no complaints | "No open complaints, nice work" | (no CTA; this is a positive empty state) |
| Ledger history, new customer | "No transactions yet" | (no CTA; informational) |

Distinguishes true empty (genuinely no data exists) from filtered empty (data exists but the current filter excludes it all) — the message and CTA differ (Clear filters only appears in the filtered-empty case).

## 2. No Data (Reports/Charts)
A report or chart with no data for the selected range shows an inline empty message within the chart/report area (not a full-page state) — "No data for this period," with the filter controls remaining visible and editable so the user can immediately adjust the range.

## 3. Offline States
- Driver App (primary offline context, D-24): a persistent, unobtrusive status indicator (not a blocking banner) shows connectivity state and sync queue depth (`05-screen-inventory.md` DR-10 Sync Status) — the app remains fully functional offline; this indicator is informational, never a gate on usable functionality.
- Dashboard and Customer App (secondary, non-critical offline handling): a dismissible banner ("You're offline — some data may be out of date") appears if connectivity is lost, with cached/last-known data still displayed rather than a blank screen; write actions are disabled with inline messaging explaining why, rather than silently failing.

## 4. Permission Denied
Reached when a user navigates (via direct link, bookmark, or a stale UI state) to a screen/action their role doesn't permit. Full-page pattern: illustration plus "You don't have access to this" plus "Contact your administrator for access" plus a link back to Home — never a blank screen or a raw status code message. Distinct from the Not Found pattern (section 5) since the two carry different corrective actions.

## 5. Error Pages
| Error Type | Pattern |
|---|---|
| Not Found | "This record doesn't exist or you don't have access to it" plus link to the relevant List screen (matches the API's deliberate not-found-not-forbidden tenant-isolation behavior, so the UI never distinguishes "doesn't exist" from "not yours to see") |
| Unexpected Server Error | "Something went wrong on our end" plus Retry button plus a visible trace id for support reference |
| Network/Timeout | Inline retry-focused state (not full-page) wherever the failure is scoped to one component rather than the whole page |

## 6. Success Screens
- Most successful actions confirm via a Toast (`20-animation-guidelines.md` section 6), not a full-screen interruption — reserved for the common, frequent case (order created, payment recorded).
- Full-screen success confirmation reserved for terminal, infrequent, high-significance moments: Delivery Confirmed (Driver App), Order placed for the first time (Customer App onboarding), Complaint Resolved with feedback submitted.

## 7. Maintenance Screens
- A platform-wide scheduled-maintenance state (rare, planned) shows a full-page message with the expected restoration time, reachable even when the API is down (a static, CDN-served fallback page, not dependent on the backend being reachable).
- Distinct from a generic server error (section 5) — maintenance is planned and communicated in advance where possible, never a surprise.

## Best Practices
- Every state in this document uses the same illustration style and messaging tone (calm, factual, action-oriented, never alarmist even for error states) across all three apps.
- Filtered-empty vs true-empty distinction is applied consistently across every List screen in the platform, not just the examples shown.

## Risks
- Offline-state UX risks feeling inconsistent between the Driver App's persistent-and-functional pattern and the Dashboard's dismissible-banner pattern — this is an intentional, documented difference (reflecting D-24's Driver-App-specific offline-first requirement vs the Dashboard's online-primary design), not an oversight, but worth flagging clearly in onboarding/training materials.

## Alternatives Considered
- A single universal "something's wrong" state for all error types — rejected; Permission Denied, Not Found, and Server Error carry different corrective actions and should never be conflated into one generic message.

## Future Scalability
- The illustration-plus-message-plus-CTA template extends directly to any new Phase 2 module's empty states without new pattern design.
