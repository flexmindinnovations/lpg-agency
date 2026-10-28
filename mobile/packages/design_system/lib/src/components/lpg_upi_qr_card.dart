import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import 'lpg_card.dart';

/// A UPI pay QR with the amount and payee beneath it (ADR-066).
///
/// The QR always sits on a white tile with a quiet zone, in dark mode and
/// high contrast too, because scanners need dark-on-light. Pure display: the
/// app fetches the image from `GET /payments/upi-qr` and hands the PNG bytes
/// in, so this package needs no API client.
class LpgUpiQrCard extends StatelessWidget {
  const LpgUpiQrCard({
    super.key,
    required this.png,
    required this.amountText,
    required this.payeeName,
    required this.upiId,
    this.title = 'Scan to pay with any UPI app',
  });

  final Uint8List png;

  /// Already formatted, e.g. `₹1,250.00`.
  final String amountText;
  final String payeeName;
  final String upiId;
  final String title;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return LpgCard(
      semanticLabel: 'UPI QR code to pay $amountText to $payeeName',
      child: Column(
        children: [
          Text(
            title,
            style: text.titleSmall?.copyWith(color: colors.textSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: LpgSpacing.md),
          Container(
            padding: const EdgeInsets.all(LpgSpacing.md),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(LpgRadius.md),
            ),
            child: Image.memory(
              png,
              width: 220,
              height: 220,
              filterQuality: FilterQuality.none,
              excludeFromSemantics: true,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          Text(amountText, style: text.headlineSmall),
          const SizedBox(height: LpgSpacing.xs),
          Text(payeeName, style: text.bodyMedium),
          const SizedBox(height: LpgSpacing.xs),
          InkWell(
            onTap: () => Clipboard.setData(ClipboardData(text: upiId)),
            borderRadius: BorderRadius.circular(LpgRadius.sm),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: LpgSpacing.sm,
                vertical: LpgSpacing.xs,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    upiId,
                    style: text.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  const SizedBox(width: LpgSpacing.xs),
                  Icon(
                    LpgIcons.copy,
                    size: LpgSizes.iconSm,
                    color: colors.textSecondary,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
