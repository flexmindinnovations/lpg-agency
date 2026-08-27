import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../auth_provider.dart';
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
              LpgCard(
                child: Row(
                  children: [
                    Icon(
                      profile.kycStatus == 'VERIFIED'
                          ? Icons.verified
                          : Icons.pending_actions,
                      color: profile.kycStatus == 'VERIFIED'
                          ? colors.statusSuccess
                          : colors.statusWarning,
                    ),
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
                            profile.kycStatus,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                              color: profile.kycStatus == 'VERIFIED'
                                  ? colors.statusSuccess
                                  : colors.statusWarning,
                            ),
                          ),
                        ],
                      ),
                    ),
                    LpgStatusBadge(
                      label: profile.kycStatus == 'VERIFIED'
                          ? 'SECURE'
                          : 'PENDING',
                      severity: profile.kycStatus == 'VERIFIED'
                          ? LpgStatusSeverity.success
                          : LpgStatusSeverity.warning,
                    ),
                  ],
                ),
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
                      onTap: () {}, // For selecting/editing in future
                      leadingIcon: address.addressType.toUpperCase() == 'HOME'
                          ? Icons.home_outlined
                          : Icons.business_outlined,
                      title: address.addressType,
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
