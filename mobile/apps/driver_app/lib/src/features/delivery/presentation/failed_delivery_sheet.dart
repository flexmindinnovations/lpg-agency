import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Mirrors the backend's `FailedDeliveryReasonCode`.
const _reasons = <(String, String)>[
  ('customer_unavailable', 'Customer unavailable'),
  ('wrong_address', 'Wrong address'),
  ('payment_refused', 'Payment refused'),
  ('vehicle_issue', 'Vehicle issue'),
  ('safety_issue', 'Safety issue'),
];

/// Mirrors `FailedDeliveryResolutionAction` (optional).
const _actions = <(String?, String)>[
  (null, 'Decide later'),
  ('reschedule', 'Reschedule'),
  ('cancel', 'Cancel the order'),
  ('return_stock', 'Return the stock'),
];

/// Collects a reason + optional resolution for a failed delivery. Pops
/// `({reason, action})` on confirm.
class FailedDeliverySheet extends StatefulWidget {
  const FailedDeliverySheet({super.key});

  @override
  State<FailedDeliverySheet> createState() => _FailedDeliverySheetState();
}

class _FailedDeliverySheetState extends State<FailedDeliverySheet> {
  String? _reason;
  String? _action;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          LpgSpacing.lg,
          0,
          LpgSpacing.lg,
          LpgSpacing.lg + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const LpgIconBox(icon: LpgIcons.warning, tone: LpgTone.danger),
                const SizedBox(width: LpgSpacing.smd),
                Expanded(
                  child: Text(
                    'Why did the delivery fail?',
                    style: text.titleMedium?.copyWith(
                      color: colors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: LpgSpacing.smd),
            RadioGroup<String>(
              groupValue: _reason,
              onChanged: (v) => setState(() => _reason = v),
              child: Column(
                children: [
                  for (final (code, label) in _reasons)
                    RadioListTile<String>(
                      contentPadding: EdgeInsets.zero,
                      value: code,
                      title: Text(label, style: text.bodyLarge),
                    ),
                ],
              ),
            ),
            const SizedBox(height: LpgSpacing.sm),
            const LpgFieldLabel('What next?'),
            const SizedBox(height: LpgSpacing.xs),
            Wrap(
              spacing: LpgSpacing.sm,
              runSpacing: LpgSpacing.sm,
              children: [
                for (final (value, label) in _actions)
                  ChoiceChip(
                    label: Text(label),
                    selected: _action == value,
                    onSelected: (_) => setState(() => _action = value),
                  ),
              ],
            ),
            const SizedBox(height: LpgSpacing.lg),
            LpgButton(
              label: 'Confirm failed delivery',
              expand: true,
              variant: LpgButtonVariant.destructive,
              icon: LpgIcons.cancel,
              onPressed: _reason == null
                  ? null
                  : () => Navigator.of(
                      context,
                    ).pop((reason: _reason!, action: _action)),
            ),
          ],
        ),
      ),
    );
  }
}
