import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
import '../../../auth_provider.dart';
import '../data/profile_provider.dart';

/// The Profile tab: the driver's identity, licence, current vehicle and
/// status from `GET /drivers/me`, plus the app's Log Out affordance.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final profileAsync = ref.watch(driverProfileProvider);

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
              child: Icon(Icons.person, size: 40, color: colors.actionPrimary),
            ),
          ),
          const SizedBox(height: 16),
          Center(
            child: profileAsync.when(
              loading: () => const LpgLoadingIndicator(),
              error: (_, _) => Text(
                'Driver',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colors.textPrimary,
                ),
              ),
              data: (p) => Column(
                children: [
                  Text(
                    p.name,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: colors.textPrimary,
                    ),
                  ),
                  if (p.phoneNumber.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      p.phoneNumber,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 32),
          profileAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (err, _) => LpgEmptyState(
              message: 'Could not load your profile.\n$err',
              icon: Icons.error_outline,
              actionLabel: 'Retry',
              onAction: () => ref.invalidate(driverProfileProvider),
            ),
            data: (p) => Column(
              children: [
                _InfoCard(
                  icon: Icons.badge_outlined,
                  label: 'Licence',
                  value: p.licenseExpiryDate == null
                      ? p.licenseNumber
                      : '${p.licenseNumber} · expires '
                            '${_date(p.licenseExpiryDate!)}',
                ),
                _InfoCard(
                  icon: Icons.local_shipping_outlined,
                  label: 'Vehicle',
                  value: p.vehicle == null
                      ? 'Not on a route'
                      : '${p.vehicle!.registrationNumber} · '
                            '${p.vehicle!.label}',
                ),
                _InfoCard(
                  icon: Icons.verified_user_outlined,
                  label: 'Status',
                  value: p.status.replaceAll('_', ' '),
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),
          LpgButton(
            label: 'Log Out',
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () async {
              // Drop this device's FCM token first so a shared handset stops
              // getting the previous driver's delivery alerts.
              await ref.read(pushNotificationServiceProvider).unregister();
              await ref.read(authControllerProvider).logout();
            },
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

  String _date(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      padding: EdgeInsets.zero,
      child: LpgListTile(leadingIcon: icon, title: label, subtitle: value),
    );
  }
}
