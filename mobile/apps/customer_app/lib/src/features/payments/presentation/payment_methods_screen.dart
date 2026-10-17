import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Payment methods management.
///
/// Saving a card or UPI ID is still a placeholder. Online payment itself
/// is live (ADR-053): customers pay on Razorpay's hosted page from an
/// order's or invoice's details screen, which needs nothing stored here.
/// The "Add" actions say so rather than pretending to save a card.
class PaymentMethodsScreen extends StatelessWidget {
  const PaymentMethodsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Methods')),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          const LpgFadeSlideIn(
            child: LpgEmptyState(
              message:
                  'No payment methods saved yet. You do not need one to pay '
                  'online.',
              icon: LpgIcons.payment,
            ),
          ),
          LpgFadeSlideIn(
            index: 1,
            child: LpgCard(
              padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
              child: Column(
                children: [
                  LpgListTile(
                    leadingIcon: LpgIcons.payment,
                    title: 'Add Credit / Debit Card',
                    showChevron: true,
                    onTap: () => _showComingSoon(context, 'Card payments'),
                  ),
                  const Divider(indent: LpgSpacing.md),
                  LpgListTile(
                    leadingIcon: LpgIcons.wallet,
                    leadingTone: LpgTone.accent,
                    title: 'Add UPI ID',
                    showChevron: true,
                    onTap: () => _showComingSoon(context, 'UPI payments'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: LpgSpacing.lg),
          const LpgFadeSlideIn(
            index: 2,
            child: LpgBanner(
              message:
                  'You can pay online (UPI, cards, net banking) from any '
                  "confirmed order's details screen, or pay the delivery "
                  'agent on delivery.',
            ),
          ),
        ],
      ),
    );
  }

  void _showComingSoon(BuildContext context, String feature) {
    LpgFeedback.showSheet<void>(
      context,
      builder: (sheetContext) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Center(
            child: LpgIconBox(icon: LpgIcons.clock, size: LpgSizes.avatarLg),
          ),
          const SizedBox(height: LpgSpacing.md),
          Text(
            '$feature are coming soon',
            textAlign: TextAlign.center,
            style: sheetContext.lpgText.titleMedium,
          ),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            "We'll let you know as soon as you can save a payment method. "
            "Until then, pay online from an order's details screen.",
            textAlign: TextAlign.center,
            style: sheetContext.lpgText.bodyMedium?.copyWith(
              color: sheetContext.lpgColors.textSecondary,
            ),
          ),
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Got it',
            onPressed: () => Navigator.of(sheetContext).pop(),
            expand: true,
          ),
        ],
      ),
    );
  }
}
