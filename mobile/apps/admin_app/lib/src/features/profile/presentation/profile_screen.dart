// Admin Profile Screen
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../auth_provider.dart';
import '../../../i18n/admin_strings.dart';
import '../../../providers.dart';
import '../data/profile_provider.dart';
import 'edit_profile_sheet.dart';
import 'profile_avatar_button.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _edit(BuildContext context, AdminProfile profile) async {
    final saved = await LpgFeedback.showSheet<bool>(
      context,
      title: context.strings.profile.editTitle,
      builder: (_) => EditProfileSheet(profile: profile),
    );
    if (saved != true || !context.mounted) return;
    LpgFeedback.showToast(
      context,
      context.strings.profile.updated,
      tone: LpgTone.success,
    );
  }

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
                        ProfileAvatarButton(
                          name: profile.displayName,
                          imageUrl: profile.avatarUrl,
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
                  const SizedBox(height: LpgSpacing.md),
                  LpgButton(
                    label: context.strings.profile.editTitle,
                    icon: LpgIcons.edit,
                    variant: LpgButtonVariant.secondary,
                    expand: true,
                    onPressed: () => _edit(context, profile),
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  Text('System Overview', style: text.titleSmall),
                  const SizedBox(height: LpgSpacing.sm),
                  if (profile.contactPhone != null)
                    LpgListTile(
                      title: context.strings.profile.contactPhone,
                      subtitle: profile.contactPhone,
                      leadingIcon: LpgIcons.phone,
                    ),
                  LpgListTile(
                    title: 'Role & Access Level',
                    subtitle: LpgFormat.sentence(profile.role),
                    leadingIcon: LpgIcons.profile,
                  ),
                ],
              ),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgThemeModePicker(
              controller: ref.read(lpgThemeModeControllerProvider),
            ),
            const SizedBox(height: LpgSpacing.md),
            const LpgListTile(
              title: 'App Version',
              subtitle: '1.0.0+1 (Admin Build)',
              leadingIcon: LpgIcons.support,
            ),
            const SizedBox(height: LpgSpacing.xxl),
            LpgButton(
              label: 'Sign Out',
              variant: LpgButtonVariant.destructive,
              expand: true,
              onPressed: () async {
                // Drop this device's FCM token first so a shared handset
                // stops getting this user's alerts; it must not block the
                // sign-out itself.
                try {
                  await ref.read(pushNotificationServiceProvider).unregister();
                } catch (_) {
                  // Best effort: nothing to show the user for this failure.
                } finally {
                  await ref.read(authControllerProvider).logout();
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}
