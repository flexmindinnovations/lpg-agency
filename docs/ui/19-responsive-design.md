# 19 — Responsive Design

## Purpose
Defines responsive support across desktop, tablet, mobile, ultra-wide, landscape/portrait, and touch devices.

## 1. Breakpoints (Dashboard, Angular)

| Breakpoint | Width | Primary Users |
|---|---|---|
| Ultra-wide | 1920px+ | AgencyAdmin/Manager multi-monitor setups; workspace uses a max-content-width constraint (not full-bleed) to avoid excessive line lengths and scattered focus |
| Desktop | 1280-1919px | Primary target for Dispatcher, Accountant, Manager, AgencyAdmin |
| Laptop | 1024-1279px | Common secondary target |
| Tablet | 768-1023px | WarehouseStaff (shared terminal), occasional Manager on-the-go |
| Mobile | below 768px | Emergency/occasional access only — not primary-optimized for staff roles |

## 2. Ultra-Wide Handling
Beyond 1920px, the Workspace content area caps at a maximum width (approximately 1600px) and centers, rather than stretching Data Grids and forms edge-to-edge — prevents excessive eye travel across a wide monitor and keeps the page-header/filter-bar pattern visually anchored.

## 3. Desktop
The primary design target for the Dashboard. Full Sidebar expanded by default, full Data Grid columns visible, multi-column KPI widget layout (`06-dashboard-layout.md` section 5).

## 4. Tablet
Sidebar collapses to off-canvas (hamburger-triggered); Data Grid remains a true grid (horizontally scrollable if needed) rather than converting to cards, since tablet width is generally sufficient for a reasonably-columned grid — the card-list conversion is reserved for mobile only (`14-data-grid-guidelines.md` section 11). This is the primary target for the Warehouse Staff persona's shared terminal use case.

## 5. Mobile (Dashboard)
The Dashboard is usable but explicitly not primary-optimized below 768px — staff roles are expected on desktop/tablet per their daily workflow (`02-user-personas.md`). Mobile Dashboard access supports: viewing KPIs, approving a pending request from a notification, checking an order/customer detail — not full Route Planning Board or bulk Data Grid operations, which gracefully redirect to a "this action works best on a larger screen" message rather than rendering a broken cramped layout.

## 6. Customer App and Driver App (Flutter, Mobile-Primary)
- Designed mobile-first for phone form factors (portrait-primary), with tablet layouts as a secondary adaptive breakpoint (larger touch targets remain, but layout uses available width for a two-column list-plus-detail pattern on tablet where useful, e.g. Order History list plus Order Detail side-by-side).
- No desktop/web target for these two apps in Phase 1 (per approved architecture, Flutter mobile-only).

## 7. Landscape vs Portrait
- Customer App: portrait-primary; landscape supported for content-reading contexts (viewing a long Order History or Ledger Statement) but booking/action flows lock to portrait to keep the large-touch-target, single-column flow consistent.
- Driver App: portrait-primary throughout — landscape is explicitly not optimized, since the Driver's core tasks (delivery confirmation, navigation) are designed around one-handed portrait use; landscape rotation is locked off to avoid an inconsistent, untested layout appearing accidentally.
- Dashboard: landscape-only by nature (desktop/tablet), no portrait consideration needed beyond the tablet breakpoint's off-canvas sidebar behavior.

## 8. Touch Devices
- All touch targets meet the minimums defined in `17-accessibility.md` section 7 (44x44dp Dashboard/tablet, 48x48dp Driver App) regardless of breakpoint.
- Hover-dependent interactions (tooltips, hover-reveal row actions in the Data Grid) always have a touch-accessible equivalent (tap-to-reveal, or the action is always-visible rather than hover-only) on any touch-capable breakpoint — hover is treated as a progressive enhancement for pointer devices, never the sole trigger.
- Drag-and-drop (Route Planning Board) has a keyboard/tap-based equivalent per `07-wireframe-specifications.md` Worked Example 1, extending the same principle to touch devices without a precise drag gesture.

## Best Practices
- Every screen is designed against its primary target breakpoint first, then verified (not redesigned) against the others — the three-tier screen templates (`07-wireframe-specifications.md`) already encode the responsive behavior expected at each tier, so responsive design is largely a template property, not a per-screen decision.
- Testing matrix includes at minimum: one ultra-wide monitor, one standard desktop, one tablet (the Warehouse Staff device class), and both target mobile OS default viewports for the Customer/Driver apps.

## Risks
- Tablet is a genuinely load-bearing breakpoint (Warehouse Staff's primary device) rather than a nice-to-have — mitigated by explicitly including it in every screen's design review, not treating it as an afterthought squeezed between desktop and mobile.

## Alternatives Considered
- A single fluid/fully-responsive layout with no discrete breakpoints — rejected; the Dashboard's Data Grid-heavy, information-dense nature benefits from discrete, tested breakpoint behaviors rather than an unpredictable fluid reflow.

## Future Scalability
- If a future Phase 2 need arises for Dashboard-equivalent functionality on mobile, the existing graceful-redirect pattern (section 5) is the extension point — expanding what's supported on mobile incrementally rather than redesigning the responsive strategy.
