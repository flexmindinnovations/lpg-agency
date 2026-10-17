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
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Methods')),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          const LpgFadeSlideIn(
            child: LpgEmptyState(
              message:
                  'No payment methods saved yet. Add a card or UPI ID to pay '
                  'for refills without cash on delivery.',
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
                  'Until online payments go live, orders are paid by cash or '
                  'UPI directly to the delivery agent.',
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
            "We'll let you know as soon as you can save a payment method "
            'and pay online.',
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
