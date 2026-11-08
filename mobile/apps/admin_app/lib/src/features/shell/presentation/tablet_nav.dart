import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../i18n/admin_strings.dart';
import '../../approvals/data/approvals_provider.dart';

/// One entry of the tablet navigation rail. [label] is the key of its name in
/// the string catalogue (`nav.<label>`).
class TabletDestination {
  const TabletDestination({
    required this.label,
    required this.icon,
    required this.selectedIcon,
    required this.path,
    this.branch,
  });

  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final String path;

  /// The tab branch this entry is, when it is one of the shell's four tabs.
  final int? branch;
}

/// The tablet rail: the busiest screens get their own entry and the rest stay
/// under More. Phones keep their four bottom tabs and never read this list.
const tabletDestinations = <TabletDestination>[
  TabletDestination(
    label: 'dashboard',
    icon: LpgIcons.home,
    selectedIcon: LpgIcons.homeFilled,
    path: '/',
    branch: 0,
  ),
  TabletDestination(
    label: 'orders',
    icon: LpgIcons.orders,
    selectedIcon: LpgIcons.ordersFilled,
    path: '/orders',
    branch: 1,
  ),
  TabletDestination(
    label: 'dispatch',
    icon: LpgIcons.truck,
    selectedIcon: LpgIcons.truckFilled,
    path: '/dispatch',
    branch: 2,
  ),
  TabletDestination(
    label: 'customers',
    icon: LpgIcons.customers,
    selectedIcon: LpgIcons.customers,
    path: '/customers',
  ),
  TabletDestination(
    label: 'invoices',
    icon: LpgIcons.invoice,
    selectedIcon: LpgIcons.invoice,
    path: '/invoices',
  ),
  TabletDestination(
    label: 'complaints',
    icon: LpgIcons.complaint,
    selectedIcon: LpgIcons.complaint,
    path: '/complaints',
  ),
  TabletDestination(
    label: 'approvals',
    icon: LpgIcons.approvals,
    selectedIcon: LpgIcons.approvals,
    path: '/approvals',
  ),
  TabletDestination(
    label: 'more',
    icon: LpgIcons.more,
    selectedIcon: LpgIcons.moreFilled,
    path: '/more',
    branch: 3,
  ),
];

const _moreIndex = 7;

/// Which rail entry a screen at [path] belongs to. Screens with no entry of
/// their own (stock, pricing, profile, ...) are reached from More.
int tabletIndexFor(String path) {
  if (path == '/' || path.isEmpty) return 0;
  const aliases = {'/order-view': 1, '/fleet': 2, '/cash-book': _moreIndex};
  for (final entry in aliases.entries) {
    if (path == entry.key || path.startsWith('${entry.key}/')) {
      return entry.value;
    }
  }
  for (var i = 1; i < tabletDestinations.length; i++) {
    final base = tabletDestinations[i].path;
    if (path == base || path.startsWith('$base/')) return i;
  }
  return _moreIndex;
}

/// The rail entries, with the pending-approvals count on Approvals.
List<LpgNavDestination> tabletNavDestinations(
  BuildContext context,
  int pendingApprovals,
) {
  final nav = context.strings.nav;
  final labels = {
    'dashboard': nav.dashboard,
    'orders': nav.orders,
    'dispatch': nav.dispatch,
    'customers': nav.customers,
    'invoices': nav.invoices,
    'complaints': nav.complaints,
    'approvals': nav.approvals,
    'more': nav.more,
  };
  return [
    for (final d in tabletDestinations)
      LpgNavDestination(
        icon: d.icon,
        selectedIcon: d.selectedIcon,
        label: labels[d.label] ?? d.label,
        badgeCount: d.path == '/approvals' ? pendingApprovals : 0,
      ),
  ];
}

/// Puts the tablet rail beside a screen that sits outside the tab shell (the
/// customer list, approvals, stock, ...), so the menu stays on screen. On a
/// phone it is the screen itself, untouched.
class AdminTabletFrame extends ConsumerWidget {
  const AdminTabletFrame({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!LpgBreakpoints.isWide(context)) return child;
    final colors = context.lpgColors;
    final pending = ref.watch(pendingCashHandoversProvider).value?.length ?? 0;
    final path = GoRouterState.of(context).uri.path;
    return Scaffold(
      body: Row(
        children: [
          LpgNavigationRail(
            destinations: tabletNavDestinations(context, pending),
            selectedIndex: tabletIndexFor(path),
            onDestinationSelected: (i) =>
                context.go(tabletDestinations[i].path),
          ),
          VerticalDivider(
            width: colors.isHighContrast ? 2 : 1,
            thickness: colors.isHighContrast ? 2 : 1,
            color: colors.isHighContrast
                ? colors.borderStrong
                : colors.borderDefault,
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}
