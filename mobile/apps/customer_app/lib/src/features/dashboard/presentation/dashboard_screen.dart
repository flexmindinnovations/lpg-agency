import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../orders/data/orders_provider.dart';
import '../../orders/presentation/order_presentation.dart';
import '../../profile/data/profile_provider.dart';
import '../data/ledger_provider.dart';
import '../data/notifications_provider.dart';

/// The Customer App's home tab.
///
/// Leads with the two things a customer opens the app for: how many empty
/// cylinders they hold, and ordering a refill. Below that, a live card for
/// any order already on its way, shortcuts to the screens people reach for
/// most, and the latest few orders.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  static const appName = 'LPG Agency';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadCount = ref.watch(unreadNotificationCountProvider).value ?? 0;
    final ordersAsync = ref.watch(ordersProvider);
    final firstName = ref
        .watch(profileProvider)
        .value
        ?.fullName
        .trim()
        .split(' ')
        .first;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const LpgBrandMark(size: LpgSizes.avatarSm),
            const SizedBox(width: LpgSpacing.smd),
            Text(appName, style: context.lpgText.titleLarge),
          ],
        ),
        actions: [
          LpgIconBadgeButton(
            icon: LpgIcons.notifications,
            tooltip: 'Notifications',
            count: unreadCount,
            onPressed: () => context.push('/notifications'),
          ),
          const SizedBox(width: LpgSpacing.sm),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(ledgerProvider);
          ref.invalidate(ordersProvider);
          ref.invalidate(unreadNotificationCountProvider);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: LpgSpacing.page,
          children: [
            LpgFadeSlideIn(child: _Greeting(firstName: firstName)),
            const SizedBox(height: LpgSpacing.md),
            const LpgFadeSlideIn(index: 1, child: _BalanceHero()),
            const SizedBox(height: LpgSpacing.md),
            LpgFadeSlideIn(
              index: 2,
              child: LpgButton(
                label: 'Order Gas Refill',
                onPressed: () => context.push('/orders/new'),
                icon: LpgIcons.refill,
                expand: true,
              ),
            ),
            ...ordersAsync.maybeWhen(
              data: (orders) {
                final active = orders.where((o) => o.isTrackable).toList();
                if (active.isEmpty) return const <Widget>[];
                return [
                  const SizedBox(height: LpgSpacing.md),
                  LpgFadeSlideIn(
                    index: 3,
                    child: _ActiveOrderCard(order: active.first),
                  ),
                ];
              },
              orElse: () => const <Widget>[],
            ),
            const LpgFadeSlideIn(
              index: 4,
              child: LpgSectionHeader(title: 'Quick actions'),
            ),
            const LpgFadeSlideIn(index: 5, child: _QuickActions()),
            LpgFadeSlideIn(
              index: 6,
              child: LpgSectionHeader(
                title: 'Recent orders',
                actionLabel: 'See all',
                onAction: () => context.go('/orders'),
              ),
            ),
            _RecentOrders(ordersAsync: ordersAsync),
          ],
        ),
      ),
    );
  }
}

class _Greeting extends StatelessWidget {
  const _Greeting({required this.firstName});

  final String? firstName;

  static String _salutation(DateTime now) {
    if (now.hour < 12) return 'Good morning';
    if (now.hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    final salutation = _salutation(DateTime.now());
    final name = firstName;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          name == null || name.isEmpty ? salutation : '$salutation, $name',
          style: context.lpgText.headlineSmall,
        ),
        const SizedBox(height: LpgSpacing.xs),
        Text(
          'Your gas, delivered safely.',
          style: context.lpgText.bodyMedium?.copyWith(
            color: context.lpgColors.textSecondary,
          ),
        ),
      ],
    );
  }
}

/// The cylinder balance on the brand gradient.
class _BalanceHero extends ConsumerWidget {
  const _BalanceHero();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final ledgerAsync = ref.watch(ledgerProvider);

    Widget caption(String value) => Text(
      value,
      style: text.bodyMedium?.copyWith(
        color: colors.onHero.withValues(alpha: 0.8),
      ),
    );

    return LpgHeroCard(
      watermark: LpgIcons.cylinder,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(LpgIcons.cylinder, size: LpgSizes.iconMd),
              const SizedBox(width: LpgSpacing.sm),
              Text(
                'Empty cylinders with you',
                style: text.labelLarge?.copyWith(color: colors.onHero),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          ledgerAsync.when(
            data: (ledger) {
              final balances = ledger?.balances ?? const [];
              final total = balances.fold<int>(0, (s, b) => s + b.quantity);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  LpgCountUp(
                    value: total,
                    style: text.displayLarge?.copyWith(color: colors.onHero),
                  ),
                  const SizedBox(height: LpgSpacing.xs),
                  caption(
                    balances.isNotEmpty
                        ? 'Across ${balances.length} cylinder '
                              '${balances.length == 1 ? 'type' : 'types'}'
                        : 'No outstanding cylinders',
                  ),
                ],
              );
            },
            loading: () => Padding(
              padding: const EdgeInsets.symmetric(vertical: LpgSpacing.sm),
              child: SizedBox(
                height: LpgSizes.iconXl,
                width: LpgSizes.iconXl,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  color: colors.onHero,
                ),
              ),
            ),
            error: (err, _) => caption('Balance unavailable right now'),
          ),
        ],
      ),
    );
  }
}

/// A delivery that is on its way right now, with a shortcut to live
/// tracking.
class _ActiveOrderCard extends StatelessWidget {
  const _ActiveOrderCard({required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: LpgTone.warning,
      onTap: () => context.push('/orders/${order.id}/track'),
      semanticLabel: '${order.reference} is out for delivery. Track it live.',
      padding: const EdgeInsets.all(LpgSpacing.md),
      child: Row(
        children: [
          const LpgIconBox(icon: LpgIcons.truck, tone: LpgTone.warning),
          const SizedBox(width: LpgSpacing.smd),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('On its way', style: context.lpgText.titleSmall),
                const SizedBox(height: LpgSpacing.xs / 2),
                Text(
                  '${order.reference} is out for delivery',
                  style: context.lpgText.bodySmall,
                ),
              ],
            ),
          ),
          Text(
            'Track',
            style: context.lpgText.labelLarge?.copyWith(
              color: colors.textPrimary,
            ),
          ),
          Icon(
            LpgIcons.chevronRight,
            size: LpgSizes.iconSm,
            color: colors.textPrimary,
          ),
        ],
      ),
    );
  }
}

class _QuickActions extends StatelessWidget {
  const _QuickActions();

  @override
  Widget build(BuildContext context) {
    final actions = [
      (LpgIcons.invoice, 'Invoices', '/orders/invoices', LpgTone.info),
      (LpgIcons.kyc, 'KYC', '/profile/kyc', LpgTone.success),
      (LpgIcons.payment, 'Payments', '/profile/payments', LpgTone.accent),
      (LpgIcons.support, 'Get help', '/support', LpgTone.primary),
    ];
    return Row(
      children: [
        for (var i = 0; i < actions.length; i++) ...[
          if (i > 0) const SizedBox(width: LpgSpacing.sm),
          Expanded(
            child: LpgQuickAction(
              icon: actions[i].$1,
              label: actions[i].$2,
              tone: actions[i].$4,
              onTap: () => context.push(actions[i].$3),
            ),
          ),
        ],
      ],
    );
  }
}

class _RecentOrders extends StatelessWidget {
  const _RecentOrders({required this.ordersAsync});

  final AsyncValue<List<OrderResponse>> ordersAsync;

  @override
  Widget build(BuildContext context) {
    return ordersAsync.when(
      data: (orders) {
        if (orders.isEmpty) {
          return const LpgCard(
            variant: LpgCardVariant.outlined,
            child: LpgListTile(
              leadingIcon: LpgIcons.orders,
              leadingTone: LpgTone.neutral,
              title: 'No recent orders',
              subtitle: 'Your refills will show up here.',
            ),
          );
        }
        // `orders` arrives sorted by `requestedDate` (the backend's own
        // list order, tuned for an operational "what's coming up" view) —
        // that's not what "recent" means here, since a customer can set a
        // requested date arbitrarily far in the future or in the past.
        // Sort by `orderNumber` instead: it's sequential and zero-padded,
        // so it reflects the order the orders were actually placed in.
        final recent = [
          ...orders,
        ]..sort((a, b) => (b.orderNumber ?? '').compareTo(a.orderNumber ?? ''));
        final shown = recent.take(3).toList();
        return LpgCard(
          padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
          child: Column(
            children: [
              for (var i = 0; i < shown.length; i++) ...[
                if (i > 0) const Divider(indent: LpgSpacing.md),
                LpgFadeSlideIn(
                  index: 7 + i,
                  child: LpgListTile(
                    leadingIcon: shown[i].statusIcon,
                    leadingTone: shown[i].statusSeverity.tone,
                    title: shown[i].reference,
                    subtitle: LpgFormat.sentence(shown[i].status),
                    trailing: Text(
                      LpgFormat.shortDate(shown[i].requestedDate),
                      style: context.lpgText.bodySmall,
                    ),
                    showChevron: true,
                    onTap: () => context.push('/orders/${shown[i].id}'),
                  ),
                ),
              ],
            ],
          ),
        );
      },
      loading: () =>
          const LpgSkeletonList(itemCount: 3, padding: EdgeInsets.zero),
      error: (error, stack) => const LpgBanner(
        tone: LpgTone.danger,
        message: 'Failed to load recent orders. Pull down to try again.',
      ),
    );
  }
}
