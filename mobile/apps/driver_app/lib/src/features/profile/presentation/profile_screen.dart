import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';

/// The Profile tab. Stage B: identity placeholder + the app's only Log Out
/// affordance + version. Stage C2 enriches the identity block from
/// `GET /drivers/me` (name, phone, licence, current vehicle).
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const SizedBox(height: 8),
          Center(
            child: CircleAvatar(
              radius: 40,
              backgroundColor: colors.actionPrimary.withValues(alpha: 0.1),
              child: Icon(
                Icons.person,
                size: 40,
                color: colors.actionPrimary,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Driver',
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: colors.textPrimary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 48),
          LpgButton(
            label: 'Log Out',
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () => ref.read(authControllerProvider).logout(),
          ),
          const SizedBox(height: 24),
          Text(
            'v1.0.0 (Build 1)',
            style: theme.textTheme.labelSmall?.copyWith(
              color: colors.textSecondary.withValues(alpha: 0.5),
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
