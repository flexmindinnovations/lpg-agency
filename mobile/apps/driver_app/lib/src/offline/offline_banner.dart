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

    return const Padding(
      padding: EdgeInsets.fromLTRB(
        LpgSpacing.md,
        LpgSpacing.sm,
        LpgSpacing.md,
        LpgSpacing.xs,
      ),
      child: LpgBanner(
        tone: LpgTone.warning,
        icon: LpgIcons.offline,
        message: 'Offline — showing last synced data',
      ),
    );
  }
}
