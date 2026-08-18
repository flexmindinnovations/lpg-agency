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
              onPressed: () => context.push('/profile/edit', extra: profileAsync.value),
            ),
        ],
      ),
      body: profileAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.error_outline, size: 48, color: colors.statusDanger),
                const SizedBox(height: 16),
                Text(
                  'Failed to load profile',
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  err.toString(),
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colors.textSecondary,
                  ),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () => ref.refresh(profileProvider),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
        data: (profile) {
          if (profile == null) {
            return const Center(child: Text('No profile data.'));
          }

          return ListView(
            padding: const EdgeInsets.all(24.0),
            children: [
              // Avatar & Basic Info
              Center(
                child: CircleAvatar(
                  radius: 40,
                  backgroundColor: colors.actionPrimary,
                  child: Text(
                    profile.fullName.isNotEmpty ? profile.fullName[0].toUpperCase() : '?',
                    style: theme.textTheme.headlineMedium?.copyWith(
                      color: colors.surfaceBase,
                      fontWeight: FontWeight.bold,
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
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: profile.kycStatus == 'VERIFIED'
                      ? colors.statusSuccess.withOpacity(0.1)
                      : colors.statusWarning.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: profile.kycStatus == 'VERIFIED'
                        ? colors.statusSuccess
                        : colors.statusWarning,
                  ),
                ),
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
              _buildDetailRow(
                context, 
                label: 'Customer Type', 
                value: profile.customerType,
                icon: Icons.person_outline,
              ),
              const SizedBox(height: 12),
              _buildDetailRow(
                context, 
                label: 'Email', 
                value: profile.email ?? 'Not provided',
                icon: Icons.email_outlined,
              ),
              if (profile.consumerNumber != null) ...[
                const SizedBox(height: 12),
                _buildDetailRow(
                  context, 
                  label: 'Consumer Number', 
                  value: profile.consumerNumber!,
                  icon: Icons.numbers_outlined,
                ),
              ],
              
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
                  TextButton(
                    onPressed: () => context.push('/profile/addresses/new', extra: profile.id),
                    child: const Text('Add New'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (profile.addresses.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    'No addresses saved yet.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                )
              else
                ...profile.addresses.map((address) => Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colors.surfaceRaised,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: address.isPrimary 
                          ? colors.actionPrimary 
                          : colors.borderDefault,
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        address.addressType.toUpperCase() == 'HOME' 
                            ? Icons.home_outlined 
                            : Icons.business_outlined,
                        color: address.isPrimary ? colors.actionPrimary : colors.textSecondary,
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  address.addressType,
                                  style: theme.textTheme.labelMedium?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: address.isPrimary ? colors.actionPrimary : colors.textPrimary,
                                  ),
                                ),
                                if (address.isPrimary) ...[
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: colors.actionPrimary.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      'PRIMARY',
                                      style: theme.textTheme.labelSmall?.copyWith(
                                        color: colors.actionPrimary,
                                        fontSize: 10,
                                      ),
                                    ),
                                  ),
                                ]
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${address.line1}${address.line2 != null ? ', ${address.line2}' : ''}\n'
                              '${address.city ?? ''}, ${address.state ?? ''} ${address.pincode ?? ''}',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                )),
                
              const SizedBox(height: 48),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () {
                    ref.read(authControllerProvider).logout();
                  },
                  style: OutlinedButton.styleFrom(
                    foregroundColor: colors.statusDanger,
                    side: BorderSide(color: colors.statusDanger),
                  ),
                  child: const Text('Log Out'),
                ),
              ),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }

  Widget _buildDetailRow(BuildContext context, {required String label, required String value, required IconData icon}) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: colors.surfaceRaised,
            shape: BoxShape.circle,
          ),
          child: Icon(icon, size: 16, color: colors.textSecondary),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              Text(
                value,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
