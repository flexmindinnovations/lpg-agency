import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../offline/delivery_mutations.dart';
import '../../../offline/pending_sync.dart';
import '../../delivery/data/active_route_provider.dart';
import '../data/van_load_provider.dart';

/// The van-load manifest for the driver's active route + a soft "Confirm
/// load" acknowledgement. Reached from the Today nudge; a full-screen task
/// under the Deliveries branch so the bottom bar stays.
class VanLoadScreen extends ConsumerWidget {
  const VanLoadScreen({super.key, required this.routeId});

  final String routeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loadAsync = ref.watch(routeLoadProvider(routeId));
    final queued =
        ref.watch(pendingSyncAggregatesProvider).value?.contains(routeId) ??
        false;

    return Scaffold(
      appBar: AppBar(title: const Text('Van load')),
      body: loadAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 4),
        error: (err, _) => LpgErrorState(
          message: 'Could not load the manifest.\n$err',
          onRetry: () => ref.invalidate(routeLoadProvider(routeId)),
        ),
        data: (load) => _Body(
          load: load,
          confirmed: load.isConfirmed || queued,
          onConfirm: () => _confirm(context, ref),
        ),
      ),
    );
  }

  Future<void> _confirm(BuildContext context, WidgetRef ref) async {
    await ref.read(deliveryMutationsProvider).confirmLoad(routeId);
    ref.invalidate(activeRouteProvider);
    ref.invalidate(pendingLoadProvider);
    if (!context.mounted) return;
    LpgFeedback.showToast(
      context,
      'Van load confirmed.',
      tone: LpgTone.success,
    );
    context.go('/');
  }
}

class _Body extends StatelessWidget {
  const _Body({
    required this.load,
    required this.confirmed,
    required this.onConfirm,
  });

  final VanLoad load;
  final bool confirmed;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final date = load.route.date;

    return ListView(
      padding: LpgSpacing.page,
      children: [
        if (confirmed) ...[
          LpgFadeSlideIn(
            child: LpgBanner(
              tone: LpgTone.success,
              icon: LpgIcons.successFilled,
              message:
                  'You confirmed this load${_on(load.route.loadConfirmedAt)}.',
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
        ],
        LpgFadeSlideIn(
          index: 1,
          child: LpgHeroCard(
            watermark: LpgIcons.inventory,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  date == null
                      ? 'On your van'
                      : 'On your van · ${LpgFormat.date(date)}',
                  style: text.titleSmall?.copyWith(color: colors.onHero),
                ),
                const SizedBox(height: LpgSpacing.sm),
                Text(
                  '${load.totalCylinders} cylinder'
                  '${load.totalCylinders == 1 ? '' : 's'}',
                  style: text.headlineMedium?.copyWith(color: colors.onHero),
                ),
              ],
            ),
          ),
        ),
        const LpgSectionHeader(title: 'Manifest'),
        LpgFadeSlideIn(
          index: 2,
          child: LpgCard(
            child: load.lines.isEmpty
                ? Text(
                    'The office recorded no cylinders for this route.',
                    style: text.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  )
                : Column(
                    children: [
                      for (final (i, line) in load.lines.indexed) ...[
                        if (i > 0) const Divider(height: LpgSpacing.lg),
                        LpgKeyValueRow(
                          icon: LpgIcons.cylinder,
                          label: line.label,
                          value: '× ${line.quantity}',
                          emphasize: true,
                        ),
                      ],
                    ],
                  ),
          ),
        ),
        const SizedBox(height: LpgSpacing.lg),
        if (!confirmed)
          LpgButton(
            label: 'Confirm load',
            icon: LpgIcons.check,
            expand: true,
            onPressed: onConfirm,
          ),
      ],
    );
  }

  static String _on(DateTime? at) =>
      at == null ? '' : ' on ${LpgFormat.date(at)}';
}
