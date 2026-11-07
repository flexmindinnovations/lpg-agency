import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// How a customer can pay. Nothing is saved here: online payment happens on
/// Razorpay's hosted page from an order's or invoice's details screen
/// (ADR-053), and everything else is settled with the delivery agent. The
/// screen used to offer "Add Credit / Debit Card" while saying no card was
/// needed (CA-16); it now just explains the options.
class PaymentMethodsScreen extends StatelessWidget {
  const PaymentMethodsScreen({super.key});

  static const _options = <(IconData, String, String)>[
    (
      LpgIcons.cash,
      'Cash on delivery',
      'Pay the delivery agent when your cylinder arrives.',
    ),
    (
      LpgIcons.wallet,
      'UPI or card on delivery',
      'Scan the agent\'s UPI code or pay by card at your door.',
    ),
    (
      LpgIcons.security,
      'Pay online',
      "Open a confirmed order or an invoice and tap Pay Online — UPI, cards "
          'and net banking, on a secure payment page.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Methods')),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          const LpgSectionHeader(title: 'Ways to pay'),
          LpgFadeSlideIn(
            child: LpgCard(
              padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
              child: Column(
                children: [
                  for (final (i, (icon, title, subtitle))
                      in _options.indexed) ...[
                    if (i > 0) const Divider(indent: LpgSpacing.md),
                    LpgListTile(
                      leadingIcon: icon,
                      title: title,
                      subtitle: subtitle,
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: LpgSpacing.lg),
          const LpgFadeSlideIn(
            index: 1,
            child: LpgBanner(
              message:
                  'You never need to save a card in the app. Your payment '
                  'details stay with the payment provider.',
            ),
          ),
        ],
      ),
    );
  }
}
