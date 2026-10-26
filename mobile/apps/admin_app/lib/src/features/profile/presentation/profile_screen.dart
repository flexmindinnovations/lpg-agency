// Admin Profile Screen
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../auth_provider.dart';
import '../data/profile_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final profileAsync = ref.watch(adminProfileProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Admin Profile')),
      body: SingleChildScrollView(
        padding: LpgSpacing.page,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            profileAsync.when(
              loading: () => const LpgSkeleton(height: 96),
              error: (err, _) => LpgErrorState(
                message: errorMessage(err),
                onRetry: () => ref.invalidate(adminProfileProvider),
              ),
              data: (profile) => Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  LpgCard(
                    child: Row(
                      children: [
                        LpgAvatar(
                          name: profile.displayName,
                          size: LpgSizes.avatarLg,
                        ),
                        const SizedBox(width: LpgSpacing.md),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                profile.displayName,
                                style: text.titleMedium,
                              ),
                              const SizedBox(height: LpgSpacing.xs),
                              Text(
                                profile.agencyName ?? 'Agency',
                                style: text.bodySmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                              if (profile.email != null)
                                Text(
                                  profile.email!,
                                  style: text.bodySmall?.copyWith(
                                    color: colors.textSecondary,
                                  ),
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
                  LpgListTile(
                    title: 'Role & Access Level',
                    subtitle: LpgFormat.sentence(profile.role),
                    leadingIcon: LpgIcons.profile,
                  ),
                ],
              ),
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
