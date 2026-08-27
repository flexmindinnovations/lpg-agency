# Customer App Modernization & Phase 19 Completion

Rebuild the Customer App UI to be modern, professional, and consistent with the LPG Agency Design System, while completing the features outlined in Phase 19.

## User Review Required

> [!IMPORTANT]
> The UI will transition to a more refined, "modern minimalist" look using the shared `design_system` components. This includes standardized cards, buttons, and navigation patterns.

## Proposed Changes

### [Component] Design System Alignment
Refactor existing screens to use the standardized components from `packages/design_system`.

#### [MODIFY] [DashboardScreen](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/dashboard/presentation/dashboard_screen.dart)
- Replace raw `Container` with `LpgCard`.
- Replace `ElevatedButton` with `LpgButton`.
- Use `LpgListTile` for recent activity.

#### [MODIFY] [OrdersScreen](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/orders/presentation/orders_screen.dart)
- Use `LpgCard` for order items.
- Use `LpgStatusBadge` for order status.
- Use `LpgEmptyState` for empty order history.

#### [MODIFY] [ProfileScreen](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/profile/presentation/profile_screen.dart)
- Modernize the profile layout using `LpgListTile` for settings.
- Group settings into cards using `LpgCard`.

---

### [Component] Phase 19 Features
Implement the missing professional features as outlined in the current phase plan.

#### [NEW] [NotificationsScreen](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/dashboard/presentation/notifications_screen.dart)
- Inbox UI for push notifications and system updates.

#### [NEW] [OrderTrackingScreen](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/orders/presentation/order_tracking_screen.dart)
- Live tracking UI with map placeholder and order milestones timeline.

#### [MODIFY] [SupportScreen](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/support/presentation/support_screen.dart)
- Rebuild the support screen to list active tickets and provide a "Raise Complaint" flow.

---

### [Component] Navigation & Shell
Refine the bottom navigation experience.

#### [MODIFY] [AppShell](file:///E:/Development/Angular/V22/lpg-agency/mobile/apps/customer_app/lib/src/features/shell/presentation/app_shell.dart)
- Ensure the `NavigationBar` uses the design system's monochromatic/modern style.

## Verification Plan

### Automated Tests
- Run `flutter test` in `apps/customer_app` to ensure no regressions in existing logic.
- Verify widget rendering using `render_compose_preview` (if available/applicable, but here it's Flutter so I'll rely on manual verification via screenshots).

### Manual Verification
- Walkthrough the app on a device/emulator to verify the "modern" look and feel.
- Verify navigation between all 4 tabs.
- Verify the "Order Gas" flow triggers the bottom sheet correctly.
- Verify the new "Support" and "Notifications" screens render as expected.
