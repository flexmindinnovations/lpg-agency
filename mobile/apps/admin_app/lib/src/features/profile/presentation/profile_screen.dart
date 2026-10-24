// Admin Profile Screen
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final auth = ref.watch(authControllerProvider);
    final principal = auth.state.principal;

    return Scaffold(
      appBar: AppBar(title: const Text('Admin Profile')),
      body: SingleChildScrollView(
        padding: LpgSpacing.page,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LpgCard(
              child: Row(
                children: [
                  const LpgAvatar(
                    name: 'Admin User',
                    size: LpgSizes.avatarLg,
                  ),
                  const SizedBox(width: LpgSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Admin Console User', style: text.titleMedium),
                        const SizedBox(height: LpgSpacing.xs),
                        Text(
                          'Agency Tenant: ${principal?.tenantId ?? 'dev-tenant'}',
                          style: text.bodySmall?.copyWith(color: colors.textSecondary),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: LpgSpacing.lg),
            Text('System Overview', style: text.titleSmall),
            const SizedBox(height: LpgSpacing.sm),
            const LpgListTile(
              title: 'Role & Access Level',
              subtitle: 'Agency Administrator / Manager',
              leadingIcon: LpgIcons.profile,
            ),
            const LpgListTile(
              title: 'App Version',
              subtitle: '1.0.0+1 (Admin Build)',
              leadingIcon: LpgIcons.support,
            ),
            const SizedBox(height: LpgSpacing.xxl),
            LpgButton(
              label: 'Sign Out',
              variant: LpgButtonVariant.destructive,
              onPressed: () => ref.read(authControllerProvider).logout(),
            ),
          ],
        ),
      ),
    );
  }
}
