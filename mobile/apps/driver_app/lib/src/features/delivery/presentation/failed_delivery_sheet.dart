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
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          24,
          0,
          24,
          24 + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Why did the delivery fail?',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: colors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            RadioGroup<String>(
              groupValue: _reason,
              onChanged: (v) => setState(() => _reason = v),
              child: Column(
                children: [
                  for (final (code, label) in _reasons)
                    RadioListTile<String>(
                      contentPadding: EdgeInsets.zero,
                      value: code,
                      title: Text(label),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'What next?',
              style: theme.textTheme.labelLarge?.copyWith(
                color: colors.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            Wrap(
              spacing: 8,
              children: [
                for (final (value, label) in _actions)
                  ChoiceChip(
                    label: Text(label),
                    selected: _action == value,
                    onSelected: (_) => setState(() => _action = value),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            LpgButton(
              label: 'Confirm failed delivery',
              expand: true,
              variant: LpgButtonVariant.secondary,
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
