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
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Could not load the manifest.\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.invalidate(routeLoadProvider(routeId)),
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
    final messenger = ScaffoldMessenger.of(context);
    await ref.read(deliveryMutationsProvider).confirmLoad(routeId);
    ref.invalidate(activeRouteProvider);
    ref.invalidate(pendingLoadProvider);
    if (!context.mounted) return;
    messenger.showSnackBar(
      const SnackBar(content: Text('Van load confirmed.')),
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
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final d = load.route.date;
    final date = d == null
        ? null
        : '${d.year}-${d.month.toString().padLeft(2, '0')}-'
              '${d.day.toString().padLeft(2, '0')}';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (confirmed) ...[
          _ConfirmedBanner(at: load.route.loadConfirmedAt),
          const SizedBox(height: 16),
        ],
        LpgCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                date == null ? 'On your van' : 'On your van · $date',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              const SizedBox(height: 12),
              if (load.lines.isEmpty)
                Text(
                  'The office recorded no cylinders for this route.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.textSecondary,
                  ),
                )
              else
                for (final line in load.lines) ...[
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        line.label,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          color: colors.textPrimary,
                        ),
                      ),
                      Text(
                        '× ${line.quantity}',
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: colors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                ],
              const Divider(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Total',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  Text(
                    '${load.totalCylinders} cylinder'
                    '${load.totalCylinders == 1 ? '' : 's'}',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: colors.textPrimary,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        if (!confirmed)
          LpgButton(
            label: 'Confirm load',
            icon: Icons.check_circle_outline,
            expand: true,
            onPressed: onConfirm,
          ),
        const SizedBox(height: 24),
      ],
    );
  }
}

class _ConfirmedBanner extends StatelessWidget {
  const _ConfirmedBanner({required this.at});

  final DateTime? at;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final when = at == null
        ? ''
        : ' on ${at!.year}-${at!.month.toString().padLeft(2, '0')}-'
              '${at!.day.toString().padLeft(2, '0')}';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.statusSuccess.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 18,
            color: colors.statusSuccess,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'You confirmed this load$when.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
