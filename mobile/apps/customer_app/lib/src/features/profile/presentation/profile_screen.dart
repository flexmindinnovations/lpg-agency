import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';
import '../data/profile_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileAsync = ref.watch(profileProvider);
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Profile',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
        actions: [
          if (profileAsync.hasValue && profileAsync.value != null)
            IconButton(
              icon: Icon(Icons.edit_outlined, color: colors.actionPrimary),
              onPressed: () =>
                  context.push('/profile/edit', extra: profileAsync.value),
            ),
        ],
      ),
      body: profileAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, stack) => LpgEmptyState(
          message: 'Failed to load profile\n${err.toString()}',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(profileProvider),
        ),
        data: (profile) {
          if (profile == null) {
            return const LpgEmptyState(message: 'No profile data found.');
          }

          return ListView(
            padding: const EdgeInsets.all(24.0),
            children: [
              // Avatar & Basic Info
              Center(
                child: Hero(
                  tag: 'profile_avatar',
                  child: CircleAvatar(
                    radius: 40,
                    backgroundColor: colors.actionPrimary,
                    child: Text(
                      profile.fullName.isNotEmpty
                          ? profile.fullName[0].toUpperCase()
                          : '?',
                      style: theme.textTheme.headlineMedium?.copyWith(
                        color: colors.textInverse,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Center(
                child: Text(
                  profile.fullName,
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colors.textPrimary,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Center(
                child: Text(
                  profile.phoneNumber,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.textSecondary,
                  ),
                ),
              ),

              const SizedBox(height: 32),

              // KYC Status Card
              Builder(
                builder: (context) {
                  final kyc = _kycDisplay(profile.kycStatus);
                  final kycColor = _severityColor(colors, kyc.severity);
                  return LpgCard(
                    child: Row(
                      children: [
                        Icon(kyc.icon, color: kycColor),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'KYC Status',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                              Text(
                                kyc.label,
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: kycColor,
                                ),
                              ),
                            ],
                          ),
                        ),
                        LpgStatusBadge(
                          label: kyc.label.toUpperCase(),
                          severity: kyc.severity,
                        ),
                      ],
                    ),
                  );
                },
              ),

              const SizedBox(height: 32),
              Text(
                'Account Details',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 16),
              LpgCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    LpgListTile(
                      leadingIcon: Icons.person_outline,
                      title: 'Customer Type',
                      subtitle: profile.customerType,
                    ),
                    Divider(height: 1, indent: 56, color: colors.borderDefault),
                    LpgListTile(
                      leadingIcon: Icons.email_outlined,
                      title: 'Email',
                      subtitle: profile.email ?? 'Not provided',
                    ),
                    if (profile.consumerNumber != null) ...[
                      Divider(
                        height: 1,
                        indent: 56,
                        color: colors.borderDefault,
                      ),
                      LpgListTile(
                        leadingIcon: Icons.numbers_outlined,
                        title: 'Consumer Number',
                        subtitle: profile.consumerNumber!,
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 32),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Saved Addresses',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colors.textPrimary,
                    ),
                  ),
                  LpgButton(
                    label: 'Add New',
                    onPressed: () => context.push(
                      '/profile/addresses/new',
                      extra: profile.id,
                    ),
                    variant: LpgButtonVariant.text,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (profile.addresses.isEmpty)
                LpgEmptyState(
                  message: 'No addresses saved yet.',
                  icon: Icons.location_off_outlined,
                )
              else
                ...profile.addresses.map(
                  (address) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
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
                      leadingIcon: switch (address.addressType.toLowerCase()) {
                        'billing' => Icons.receipt_long_outlined,
                        'both' => Icons.done_all,
                        _ => Icons.local_shipping_outlined,
                      },
                      title: address.addressType.isEmpty ? '' : address.addressType[0].toUpperCase() + address.addressType.substring(1),
                      subtitle:
                          '${address.line1}${address.line2 != null ? ', ${address.line2}' : ''}\n'
                          '${address.city ?? ''}, ${address.state ?? ''} ${address.pincode ?? ''}',
                      trailing: address.isPrimary
                          ? const LpgStatusBadge(
                              label: 'PRIMARY',
                              severity: LpgStatusSeverity.info,
                            )
                          : null,
                    ),
                  ),
                ),

              const SizedBox(height: 32),
              Text(
                'Payment Methods',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              LpgCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    LpgListTile(
                      leadingIcon: Icons.credit_card_outlined,
                      title: 'Saved Cards',
                      subtitle: 'No cards saved',
                      onTap: () {},
                    ),
                    Divider(height: 1, indent: 56, color: colors.borderDefault),
                    LpgListTile(
                      leadingIcon: Icons.account_balance_wallet_outlined,
                      title: 'UPI / Wallet',
                      subtitle: 'Manage digital payments',
                      onTap: () {},
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 48),
              LpgButton(
                label: 'Log Out',
                onPressed: () => ref.read(authControllerProvider).logout(),
                variant: LpgButtonVariant.secondary,
                expand: true,
              ),
              const SizedBox(height: 24),
            ],
          );
        },
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
    icon: Icons.verified,
    severity: LpgStatusSeverity.success,
  ),
  'rejected' => (
    label: 'Rejected',
    icon: Icons.error_outline,
    severity: LpgStatusSeverity.danger,
  ),
  'expired' => (
    label: 'Expired',
    icon: Icons.schedule_outlined,
    severity: LpgStatusSeverity.warning,
  ),
  _ => (
    label: 'Pending',
    icon: Icons.pending_actions,
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
  final colors = Theme.of(context).extension<LpgColors>()!;
  await showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (sheetContext) => Container(
      decoration: BoxDecoration(
        color: Theme.of(sheetContext).scaffoldBackgroundColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: colors.borderDefault,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 24),
          LpgListTile(
            leadingIcon: Icons.edit_outlined,
            title: 'Edit Address',
            onTap: () {
              Navigator.of(sheetContext).pop();
              context.push(
                '/profile/addresses/${address.id}/edit',
                extra: (customerId: customerId, address: address),
              );
            },
          ),
          if (!address.isPrimary) ...[
            const SizedBox(height: 8),
            LpgListTile(
              leadingIcon: Icons.star_outline,
              title: 'Set as Primary',
              onTap: () {
                Navigator.of(sheetContext).pop();
                _setPrimaryAddress(context, ref, customerId, address.id);
              },
            ),
          ],
        ],
      ),
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
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Primary address updated.')));
    },
    onFailure: (failure) => ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Could not update: ${failure.message}')),
    ),
  );
}

Color _severityColor(LpgColors colors, LpgStatusSeverity severity) =>
    switch (severity) {
      LpgStatusSeverity.success => colors.statusSuccess,
      LpgStatusSeverity.warning => colors.statusWarning,
      LpgStatusSeverity.danger => colors.statusDanger,
      LpgStatusSeverity.info => colors.statusInfo,
      LpgStatusSeverity.neutral => colors.textSecondary,
    };
