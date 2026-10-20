import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/orders_provider.dart';

/// The code the customer gives the driver at the door, on the order and
/// tracking screens while the order is out for delivery (CA-04). The same
/// code is sent by SMS; showing it here means a late or missing SMS never
/// leaves the driver waiting.
///
/// Renders nothing until a code exists, and nothing if it can't be read —
/// the SMS is still the fallback.
class DeliveryCodeCard extends ConsumerWidget {
  const DeliveryCodeCard({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final codeAsync = ref.watch(deliveryCodeProvider(orderId));
    return codeAsync.when(
      loading: () => const Padding(
        padding: EdgeInsets.only(bottom: LpgSpacing.md),
        child: LpgSkeleton(height: LpgSizes.avatarLg),
      ),
      error: (_, _) => const SizedBox.shrink(),
      data: (code) => code == null
          ? const SizedBox.shrink()
          : Padding(
              padding: const EdgeInsets.only(bottom: LpgSpacing.md),
              child: _CodeCard(code: code),
            ),
    );
  }
}

class _CodeCard extends StatelessWidget {
  const _CodeCard({required this.code});

  final String code;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: LpgTone.primary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const LpgIconBox(icon: LpgIcons.lock),
              const SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: Semantics(
                  header: true,
                  child: Text('Delivery code', style: text.titleMedium),
                ),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          Semantics(
            // Read digit by digit, the way the customer will say it.
            label: 'Delivery code ${code.split('').join(' ')}',
            excludeSemantics: true,
            child: Text(
              code,
              key: const Key('delivery-code'),
              style: text.displaySmall?.copyWith(
                color: colors.textPrimary,
                fontFeatures: const [FontFeature.tabularFigures()],
                letterSpacing: LpgSpacing.sm,
              ),
            ),
          ),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            'Tell the driver this code only after you have checked the '
            "cylinder's seal and weight. The same code was sent to you by "
            'SMS.',
            style: text.bodySmall?.copyWith(color: colors.textSecondary),
          ),
        ],
      ),
    );
  }
}
