import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'connectivity.dart';

/// A thin strip shown while the device is offline: the driver is looking at
/// the last synced data and any actions they take are queued.
class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final online = ref.watch(connectivityProvider).value ?? true;
    if (online) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;

    return Container(
      width: double.infinity,
      color: colors.statusWarning.withValues(alpha: 0.16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Icon(Icons.cloud_off_outlined, size: 16, color: colors.statusWarning),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Offline — showing last synced data',
              style: theme.textTheme.labelMedium?.copyWith(
                color: colors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
