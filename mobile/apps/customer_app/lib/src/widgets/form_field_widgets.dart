import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// An uppercase field label matching [LpgTextField]'s own label style —
/// pulled out here so screens with plain (non-text-field) form controls,
/// like [FormDropdownField], can label them consistently with the fields
/// around them.
class FieldLabel extends StatelessWidget {
  const FieldLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        text.toUpperCase(),
        style: theme.textTheme.labelSmall?.copyWith(
          color: colors.textSecondary,
          fontWeight: FontWeight.bold,
          letterSpacing: 1.1,
        ),
      ),
    );
  }
}

/// A bordered dropdown matching [LpgTextField]'s visual language — no
/// dropdown component exists in `design_system` yet (nothing there needs
/// one outside app-level forms), so this lives here instead, shared across
/// the app's forms rather than duplicated per screen.
class FormDropdownField<T> extends StatelessWidget {
  const FormDropdownField({
    super.key,
    required this.value,
    required this.items,
    required this.onChanged,
    this.placeholder,
  });

  final T value;
  final Map<T, String> items;
  final String? placeholder;
  final void Function(T?) onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.borderDefault),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButtonFormField<T>(
          initialValue: value,
          isExpanded: true,
          decoration: const InputDecoration(border: InputBorder.none),
          icon: Icon(Icons.expand_more, color: colors.textSecondary),
          style: TextStyle(color: colors.textPrimary, fontSize: 16),
          dropdownColor: colors.surfaceRaised,
          items: [
            if (placeholder != null)
              DropdownMenuItem<T>(value: null, child: Text(placeholder!)),
            ...items.entries.map(
              (e) => DropdownMenuItem<T>(value: e.key, child: Text(e.value)),
            ),
          ],
          onChanged: onChanged,
        ),
      ),
    );
  }
}
