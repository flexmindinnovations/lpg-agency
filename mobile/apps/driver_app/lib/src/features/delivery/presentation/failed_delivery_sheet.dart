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

/// Longest note the backend accepts (`FAILED_DELIVERY_NOTE_MAX_LENGTH`).
const failedDeliveryNoteMaxLength = 500;

/// Collects a reason, an optional resolution and an optional note for a
/// failed delivery. Pops `({reason, action, note})` on confirm. The five
/// reasons are fixed (D-12); anything they don't cover goes in the note.
class FailedDeliverySheet extends StatefulWidget {
  const FailedDeliverySheet({super.key});

  @override
  State<FailedDeliverySheet> createState() => _FailedDeliverySheetState();
}

class _FailedDeliverySheetState extends State<FailedDeliverySheet> {
  String? _reason;
  String? _action;
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;

    // The title, handle, padding and keyboard clearance come from
    // `LpgFeedback.showSheet`, which opens this.
    return LpgSheetLayout(
      body: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
          LpgChoiceChips<String?>(
            options: {for (final (value, label) in _actions) value: label},
            selected: _action,
            onSelected: (value) => setState(() => _action = value),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Note (optional)',
            hintText: 'e.g. Gate locked, customer asked for Saturday',
            controller: _note,
            maxLines: 3,
            maxLength: failedDeliveryNoteMaxLength,
            textCapitalization: TextCapitalization.sentences,
          ),
        ],
      ),
      footer: LpgSheetActions(
        primaryLabel: 'Confirm failed delivery',
        primaryVariant: LpgButtonVariant.destructive,
        primaryIcon: LpgIcons.cancel,
        onPrimary: _reason == null
            ? null
            : () => Navigator.of(context).pop((
                reason: _reason!,
                action: _action,
                note: _note.text.trim().isEmpty ? null : _note.text.trim(),
              )),
      ),
    );
  }
}
