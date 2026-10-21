import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_provider.dart';
import '../../../auth_provider.dart';
import '../../../offline/cached_resource.dart';
import '../../../offline/sync_providers.dart';
import '../data/profile_provider.dart';

/// The Profile tab: the driver's identity, licence, current vehicle and
/// status from `GET /drivers/me`, plus the app's Log Out affordance.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final profileAsync = ref.watch(driverProfileProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          LpgFadeSlideIn(
            child: _Header(
              name: profileAsync.value?.name,
              phone: profileAsync.value?.phoneNumber,
              loading: profileAsync.isLoading,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          profileAsync.when(
            loading: () =>
                const LpgSkeletonList(itemCount: 3, padding: EdgeInsets.zero),
            error: (err, _) => LpgErrorState(
              message: 'Could not load your profile.\n$err',
              onRetry: () => ref.invalidate(driverProfileProvider),
            ),
            data: (p) => LpgFadeSlideIn(
              index: 1,
              child: LpgCard(
                padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
                child: Column(
                  children: [
                    LpgListTile(
                      leadingIcon: LpgIcons.kyc,
                      title: 'Licence',
                      subtitle: p.licenseExpiryDate == null
                          ? p.licenseNumber
                          : '${p.licenseNumber} · expires '
                                '${LpgFormat.date(p.licenseExpiryDate!)}',
                    ),
                    const Divider(indent: LpgSpacing.md),
                    LpgListTile(
                      leadingIcon: LpgIcons.truck,
                      leadingTone: LpgTone.accent,
                      title: 'Vehicle',
                      subtitle: p.vehicle == null
                          ? 'Not on a route'
                          : '${p.vehicle!.registrationNumber} · '
                                '${p.vehicle!.label}',
                    ),
                    const Divider(indent: LpgSpacing.md),
                    LpgListTile(
                      leadingIcon: LpgIcons.verified,
                      leadingTone: LpgTone.success,
                      title: 'Status',
                      subtitle: LpgFormat.sentence(p.status),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const LpgSectionHeader(title: 'Offline sync'),
          LpgFadeSlideIn(
            index: 2,
            child: _SyncStatusRow(
              pending: ref.watch(pendingSyncCountProvider).value ?? 0,
              issues: ref.watch(syncIssuesProvider).value?.length ?? 0,
            ),
          ),
          const SizedBox(height: LpgSpacing.xl),
          LpgButton(
            label: 'Log Out',
            icon: LpgIcons.logout,
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () async {
              final confirmed = await LpgFeedback.confirm(
                context,
                title: 'Log out?',
                message:
                    "You'll need the agency code, your mobile number and a "
                    'new code to sign in again.',
                confirmLabel: 'Log Out',
              );
              if (!confirmed) return;
              // Drop this device's FCM token first so a shared handset stops
              // getting the previous driver's delivery alerts, and clear the
              // offline read cache so the next driver never sees this one's
              // route/stop data. Neither may block the sign-out itself.
              try {
                await ref.read(pushNotificationServiceProvider).unregister();
                await ref.read(resourceCacheProvider)?.clear();
              } catch (e) {
                debugPrint('logout: cleanup failed ($e)');
              } finally {
                await ref.read(authControllerProvider).logout();
              }
            },
          ),
          const SizedBox(height: LpgSpacing.lg),
          Text(
            'v1.0.0 (Build 1)',
            style: context.lpgText.labelSmall?.copyWith(
              color: colors.textDisabled,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

/// Avatar, name and phone. Falls back to "Driver" when the profile can't
/// load, so the screen still reads sensibly offline.
class _Header extends StatelessWidget {
  const _Header({
    required this.name,
    required this.phone,
    required this.loading,
  });

  final String? name;
  final String? phone;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final displayName = name ?? (loading ? '' : 'Driver');
    return Row(
      children: [
        LpgAvatar(name: displayName, size: LpgSizes.avatarLg),
        const SizedBox(width: LpgSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (loading)
                const LpgShimmer(
                  child: LpgSkeleton(width: LpgSizes.avatarLg * 2),
                )
              else
                Text(displayName, style: text.titleLarge),
              if (phone case final phone? when phone.isNotEmpty) ...[
                const SizedBox(height: LpgSpacing.xs),
                Text(
                  phone,
                  style: text.bodyMedium?.copyWith(
                    color: context.lpgColors.textSecondary,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _SyncStatusRow extends StatelessWidget {
  const _SyncStatusRow({required this.pending, required this.issues});

  final int pending;
  final int issues;

  @override
  Widget build(BuildContext context) {
    final subtitle = issues > 0
        ? '$issues need${issues == 1 ? 's' : ''} your attention'
        : pending > 0
        ? '$pending change${pending == 1 ? '' : 's'} syncing'
        : 'All changes synced';
    final tone = issues > 0
        ? LpgTone.danger
        : pending > 0
        ? LpgTone.warning
        : LpgTone.success;

    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: () => context.goNamed('sync'),
      child: LpgListTile(
        leadingIcon: issues > 0
            ? LpgIcons.syncProblem
            : pending > 0
            ? LpgIcons.sync
            : LpgIcons.synced,
        leadingTone: tone,
        title: 'Sync status',
        subtitle: subtitle,
        showChevron: true,
      ),
    );
  }
}
