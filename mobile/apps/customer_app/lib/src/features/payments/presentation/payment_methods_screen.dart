import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Payment methods management.
///
/// A deliberate UI placeholder: the platform has no payment-gateway
/// integration yet (Phase 19 plan — "Payment Gateways ... remain a UI
/// placeholder"), so there is nothing to persist and the "Add" actions
/// explain that rather than pretending to save a card. The screen still
/// exists as its own route so the shape is in place for when a gateway
/// (Razorpay/UPI) is wired in a later phase.
class PaymentMethodsScreen extends StatelessWidget {
  const PaymentMethodsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Payment Methods',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24.0),
        children: [
          const LpgEmptyState(
            message:
                'No payment methods saved yet. Add a card or UPI ID to pay '
                'for refills without cash on delivery.',
            icon: Icons.credit_card_off_outlined,
          ),
          const SizedBox(height: 24),
          LpgCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                LpgListTile(
                  leadingIcon: Icons.credit_card_outlined,
                  title: 'Add Credit / Debit Card',
                  onTap: () => _showComingSoon(context, 'Card payments'),
                ),
                Divider(height: 1, indent: 56, color: colors.borderDefault),
                LpgListTile(
                  leadingIcon: Icons.account_balance_wallet_outlined,
                  title: 'Add UPI ID',
                  onTap: () => _showComingSoon(context, 'UPI payments'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Until online payments go live, orders are paid by cash or UPI '
            'directly to the delivery agent.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  void _showComingSoon(BuildContext context, String feature) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);
        return Container(
          decoration: BoxDecoration(
            color: theme.scaffoldBackgroundColor,
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
              Icon(Icons.schedule_outlined, size: 40, color: colors.actionPrimary),
              const SizedBox(height: 16),
              Text(
                '$feature are coming soon',
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                "We'll let you know as soon as you can save a payment method "
                'and pay online.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              const SizedBox(height: 24),
              LpgButton(
                label: 'Got it',
                onPressed: () => Navigator.of(sheetContext).pop(),
                expand: true,
              ),
            ],
          ),
        );
      },
    );
  }
}
