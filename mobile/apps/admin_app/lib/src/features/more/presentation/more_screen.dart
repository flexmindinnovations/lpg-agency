import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/admin_app_bar.dart';
import '../../approvals/data/approvals_provider.dart';
import '../../dashboard/data/dashboard_providers.dart';

/// One row of the More menu.
class _MoreItem {
  const _MoreItem({
    required this.icon,
    required this.label,
    required this.hint,
    required this.routeName,
    this.badge = 0,
  });

  final IconData icon;
  final String label;
  final String hint;
  final String routeName;
  final int badge;
}

/// Everything that does not earn a bottom-bar tab, grouped by what the owner
/// is trying to do. Modules appear here as they are built.
class MoreScreen extends ConsumerWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending = ref.watch(pendingCashHandoversProvider).value?.length ?? 0;
    final openComplaints =
        ref.watch(operationsSnapshotProvider).value?.openComplaints ?? 0;

    final groups = <(String, List<_MoreItem>)>[
      (
        'Customers and billing',
        [
          const _MoreItem(
            icon: LpgIcons.customers,
            label: 'Customers',
            hint: 'Search, balances and cylinders held',
            routeName: 'customers',
          ),
          const _MoreItem(
            icon: LpgIcons.invoice,
            label: 'Invoices',
            hint: 'Dues, payments and reminders',
            routeName: 'invoices',
          ),
          _MoreItem(
            icon: LpgIcons.complaint,
            label: 'Complaints',
            hint: 'Assign, resolve and meet deadlines',
            routeName: 'complaints',
            badge: openComplaints,
          ),
        ],
      ),
      (
        'Team and money',
        [
          _MoreItem(
            icon: LpgIcons.approvals,
            label: 'Approvals',
            hint: 'Driver cash handovers to review',
            routeName: 'approvals',
            badge: pending,
          ),
          const _MoreItem(
            icon: LpgIcons.van,
            label: 'Drivers and vans',
            hint: 'Add, edit and check documents',
            routeName: 'fleet',
          ),
        ],
      ),
      (
        'Account',
        [
          const _MoreItem(
            icon: LpgIcons.profile,
            label: 'Profile and settings',
            hint: 'Your account, theme and sign out',
            routeName: 'profile',
          ),
        ],
      ),
    ];

    return Scaffold(
      appBar: const AdminAppBar(title: 'More', showSearch: true),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          for (final (heading, items) in groups) ...[
            Padding(
              padding: const EdgeInsets.only(
                top: LpgSpacing.md,
                bottom: LpgSpacing.sm,
              ),
              child: Text(
                heading.toUpperCase(),
                style: context.lpgText.labelSmall?.copyWith(
                  color: context.lpgColors.textSecondary,
                  letterSpacing: 0.8,
                ),
              ),
            ),
            LpgGroupedList(
              children: [for (final item in items) _MoreTile(item: item)],
            ),
          ],
        ],
      ),
    );
  }
}

class _MoreTile extends StatelessWidget {
  const _MoreTile({required this.item});

  final _MoreItem item;

  @override
  Widget build(BuildContext context) {
    return LpgListTile(
      leadingIcon: item.icon,
      title: item.label,
      subtitle: item.hint,
      trailing: item.badge > 0 ? Badge(label: Text('${item.badge}')) : null,
      showChevron: true,
      onTap: () => context.pushNamed(item.routeName),
    );
  }
}
