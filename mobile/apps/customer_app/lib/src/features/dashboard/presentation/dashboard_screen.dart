import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../orders/presentation/order_bottom_sheet.dart';

/// The main dashboard for the Customer App.
///
/// Implements a stark, minimalist aesthetic inspired by modern apps (e.g. ChatGPT).
/// Focuses purely on the current balance and the primary action: ordering gas.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'LPG Flow',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.notifications_outlined, color: colors.textPrimary),
            onPressed: () {
              // TODO: Navigate to notifications screen
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 24),
            // Location Header
            Row(
              children: [
                Icon(
                  Icons.location_on_outlined,
                  size: 16,
                  color: colors.textSecondary,
                ),
                const SizedBox(width: 8),
                Text(
                  'HOME',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: colors.textSecondary,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Main Balance Card
            Container(
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(
                color: colors.surfaceRaised,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: colors.borderDefault),
              ),
              child: Column(
                children: [
                  Text(
                    'Current Gas Balance',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    '24.5 kg',
                    style: theme.textTheme.displayMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: colors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Full: 40 kg | Standard Connection',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 32),

            // Primary Action Button (Pill shaped)
            ElevatedButton(
              onPressed: () => _showOrderSheet(context),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('Order Gas'),
                  SizedBox(width: 8),
                  Icon(Icons.local_gas_station_outlined, size: 20),
                ],
              ),
            ),

            const SizedBox(height: 48),

            // Recent Activity Section
            Text(
              'Recent Activity',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: colors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),

            _buildActivityItem(
              context: context,
              icon: Icons.local_gas_station_outlined,
              title: 'Ordered 14 kg',
              date: 'Oct 12',
            ),
            const SizedBox(height: 12),
            _buildActivityItem(
              context: context,
              icon: Icons.account_balance_wallet_outlined,
              title: 'Balance Refilled',
              date: 'Oct 01',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActivityItem({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String date,
  }) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: colors.surfaceRaised,
            shape: BoxShape.circle,
            border: Border.all(color: colors.borderDefault),
          ),
          child: Icon(icon, size: 16, color: colors.textSecondary),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Text(
            title,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colors.textPrimary,
            ),
          ),
        ),
        Text(
          date,
          style: theme.textTheme.bodySmall?.copyWith(
            color: colors.textSecondary,
          ),
        ),
      ],
    );
  }

  void _showOrderSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const OrderBottomSheet(),
    );
  }
}
