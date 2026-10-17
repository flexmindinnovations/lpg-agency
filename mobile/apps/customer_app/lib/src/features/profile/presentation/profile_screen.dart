import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';
import '../data/profile_provider.dart';

/// `line1[, line2]` on the first line, `city, state pincode` on the second —
/// each piece only included (and each joining comma/space only added) when
/// it's actually present, so a partial address (city/state/pincode all
/// blank, as a freshly-added address can be before the customer fills them
/// in) doesn't render a lone dangling `,` where the second line would go.
String _formatAddressSubtitle(CustomerAddressResponse address) {
  final line2 = address.line2;
  final firstLine = (line2 != null && line2.isNotEmpty)
      ? '${address.line1}, $line2'
      : address.line1;

  final stateAndPincode = [
    address.state,
    address.pincode,
  ].where((s) => s != null && s.isNotEmpty).join(' ');
  final secondLine = [
    address.city,
    stateAndPincode,
  ].where((s) => s != null && s.isNotEmpty).join(', ');

  return secondLine.isEmpty ? firstLine : '$firstLine\n$secondLine';
}

/// The customer's account: who they are, their KYC standing, saved
/// delivery addresses and payment methods, and sign-out.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileAsync = ref.watch(profileProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          if (profileAsync.hasValue && profileAsync.value != null)
            IconButton(
              icon: const Icon(LpgIcons.edit),
              tooltip: 'Edit profile',
              onPressed: () =>
                  context.push('/profile/edit', extra: profileAsync.value),
            ),
        ],
      ),
      body: profileAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 5),
        error: (err, stack) => LpgErrorState(
          message: 'Failed to load profile\n${err.toString()}',
          onRetry: () => ref.invalidate(profileProvider),
        ),
        data: (profile) {
          if (profile == null) {
            return const LpgEmptyState(
              message: 'No profile data found.',
              icon: LpgIcons.userOff,
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(profileProvider),
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: LpgSpacing.page,
              children: [
                LpgFadeSlideIn(child: _ProfileHeader(profile: profile)),
                const SizedBox(height: LpgSpacing.md),
                LpgFadeSlideIn(
                  index: 1,
                  child: _KycCard(status: profile.kycStatus),
                ),
                const LpgSectionHeader(title: 'Account details'),
                LpgFadeSlideIn(
                  index: 2,
                  child: LpgCard(
                    padding: const EdgeInsets.symmetric(
                      vertical: LpgSpacing.xs,
                    ),
                    child: Column(
                      children: [
                        LpgListTile(
                          leadingIcon: LpgIcons.user,
                          title: 'Customer type',
                          subtitle: LpgFormat.sentence(profile.customerType),
                        ),
                        const Divider(indent: LpgSpacing.md),
                        LpgListTile(
                          leadingIcon: LpgIcons.email,
                          title: 'Email',
                          subtitle: profile.email ?? 'Not provided',
                        ),
                        if (profile.consumerNumber != null) ...[
                          const Divider(indent: LpgSpacing.md),
                          LpgListTile(
                            leadingIcon: LpgIcons.number,
                            title: 'Consumer number',
                            subtitle: profile.consumerNumber!,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                LpgSectionHeader(
                  title: 'Saved addresses',
                  actionLabel: 'Add new',
                  onAction: () =>
                      context.push('/profile/addresses/new', extra: profile.id),
                ),
                if (profile.addresses.isEmpty)
                  const LpgCard(
                    variant: LpgCardVariant.outlined,
                    child: LpgListTile(
                      leadingIcon: LpgIcons.locationOff,
                      leadingTone: LpgTone.neutral,
                      title: 'No addresses saved yet.',
                      subtitle: 'Add one so we know where to deliver.',
                    ),
                  )
                else
                  for (final (i, address) in profile.addresses.indexed)
                    Padding(
                      padding: const EdgeInsets.only(bottom: LpgSpacing.smd),
                      child: LpgFadeSlideIn(
                        index: 3 + i,
                        child: LpgCard(
                          padding: EdgeInsets.zero,
                          child: LpgListTile(
                            onTap: () => _showAddressActions(
                              context,
                              ref,
                              profile.id,
                              address,
                            ),
                            // Real values are 'delivery'/'billing'/'both'
                            // (domain/customer/customer.py:133) -- 'home' was
                            // never one of them, so this never actually matched.
                            leadingIcon: switch (address.addressType
                                .toLowerCase()) {
                              'billing' => LpgIcons.receipt,
                              'both' => LpgIcons.allDone,
                              _ => LpgIcons.truck,
                            },
                            title: LpgFormat.sentence(address.addressType),
                            subtitle: _formatAddressSubtitle(address),
                            trailing: address.isPrimary
                                ? const LpgStatusBadge(
                                    label: 'PRIMARY',
                                    severity: LpgStatusSeverity.info,
                                  )
                                : null,
                          ),
                        ),
                      ),
                    ),
                const LpgSectionHeader(title: 'Payment methods'),
                LpgCard(
                  padding: EdgeInsets.zero,
                  child: LpgListTile(
                    leadingIcon: LpgIcons.payment,
                    leadingTone: LpgTone.accent,
                    title: 'Cards & UPI',
                    subtitle: 'No payment methods saved',
                    showChevron: true,
                    onTap: () => context.push('/profile/payments'),
                  ),
                ),
                const SizedBox(height: LpgSpacing.xl),
                LpgButton(
                  label: 'Log Out',
                  icon: LpgIcons.logout,
                  onPressed: () async {
                    // Drop the FCM token first, while the session is still
                    // valid — a shared device shouldn't keep getting this
                    // user's notifications.
                    await ref
                        .read(pushNotificationServiceProvider)
                        .unregister();
                    await ref.read(authControllerProvider).logout();
                  },
                  variant: LpgButtonVariant.secondary,
                  expand: true,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({required this.profile});

  final CustomerResponse profile;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    return Row(
      children: [
        Hero(
          tag: 'profile_avatar',
          child: LpgAvatar(name: profile.fullName, size: LpgSizes.avatarLg),
        ),
        const SizedBox(width: LpgSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(profile.fullName, style: text.titleLarge),
              const SizedBox(height: LpgSpacing.xs),
              Text(
                profile.phoneNumber,
                style: text.bodyMedium?.copyWith(
                  color: context.lpgColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _KycCard extends StatelessWidget {
  const _KycCard({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final kyc = _kycDisplay(status);
    final tone = kyc.severity.tone;
    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: tone,
      onTap: () => context.push('/profile/kyc'),
      semanticLabel: 'KYC status: ${kyc.label}. Open KYC details.',
      child: Row(
        children: [
          LpgIconBox(icon: kyc.icon, tone: tone),
          const SizedBox(width: LpgSpacing.smd),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('KYC status', style: context.lpgText.bodySmall),
                const SizedBox(height: LpgSpacing.xs / 2),
                Text(kyc.label, style: context.lpgText.titleMedium),
              ],
            ),
          ),
          Icon(
            LpgIcons.chevronRight,
            size: LpgSizes.iconMd,
            color: context.lpgColors.textSecondary,
          ),
        ],
      ),
    );
  }
}

/// Maps the backend's raw `kyc_status` (`domain/customer/customer.py`:
/// `"pending"`/`"verified"`/`"rejected"`/`"expired"`, always lowercase) to
/// display copy. Comparing against the raw value directly — the bug this
/// replaces — compared it to `'VERIFIED'` (uppercase), which could never
/// match a backend value that's never anything but lowercase: the status
/// badge and icon always fell back to "pending" styling regardless of the
/// real status, while the plain-text label right next to them printed the
/// unstyled raw backend string, so the two visibly disagreed.
({String label, IconData icon, LpgStatusSeverity severity}) _kycDisplay(
  String status,
) => switch (status.toLowerCase()) {
  'verified' => (
    label: 'Verified',
    icon: LpgIcons.verified,
    severity: LpgStatusSeverity.success,
  ),
  'rejected' => (
    label: 'Rejected',
    icon: LpgIcons.error,
    severity: LpgStatusSeverity.danger,
  ),
  'expired' => (
    label: 'Expired',
    icon: LpgIcons.clock,
    severity: LpgStatusSeverity.warning,
  ),
  _ => (
    label: 'Pending',
    icon: LpgIcons.pending,
    severity: LpgStatusSeverity.warning,
  ),
};

/// Bottom-sheet action menu for a saved address — Edit always, "Set as
/// Primary" only when this isn't already the primary address. No delete
/// action here: the backend has no `DELETE /customers/{id}/addresses/{id}`
/// route (only `PUT` update and `PUT .../primary` exist), so there's
/// nothing for a delete action to call yet.
Future<void> _showAddressActions(
  BuildContext context,
  WidgetRef ref,
  String customerId,
  CustomerAddressResponse address,
) async {
  await LpgFeedback.showSheet<void>(
    context,
    title: 'Address',
    builder: (sheetContext) => Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        LpgListTile(
          leadingIcon: LpgIcons.edit,
          title: 'Edit Address',
          onTap: () {
            Navigator.of(sheetContext).pop();
            context.push(
              '/profile/addresses/${address.id}/edit',
              extra: (customerId: customerId, address: address),
            );
          },
        ),
        if (!address.isPrimary)
          LpgListTile(
            leadingIcon: LpgIcons.star,
            leadingTone: LpgTone.accent,
            title: 'Set as Primary',
            onTap: () {
              Navigator.of(sheetContext).pop();
              _setPrimaryAddress(context, ref, customerId, address.id);
            },
          ),
      ],
    ),
  );
}

Future<void> _setPrimaryAddress(
  BuildContext context,
  WidgetRef ref,
  String customerId,
  String addressId,
) async {
  final result = await ref
      .read(customerApiProvider)
      .setPrimaryAddress(customerId, addressId);
  if (!context.mounted) return;
  result.when(
    onSuccess: (_) {
      ref.invalidate(profileProvider);
      LpgFeedback.showToast(
        context,
        'Primary address updated.',
        tone: LpgTone.success,
      );
    },
    onFailure: (failure) => LpgFeedback.showToast(
      context,
      'Could not update: ${failure.message}',
      tone: LpgTone.danger,
    ),
  );
}
