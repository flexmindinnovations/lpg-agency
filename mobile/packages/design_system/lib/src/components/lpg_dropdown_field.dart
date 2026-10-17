import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import 'lpg_text_field.dart';

/// A labelled dropdown that looks exactly like [LpgTextField] (same fill,
/// border, radius and focus colour, all from the theme's
/// `inputDecorationTheme`).
///
/// [items] maps each value to its display text. [placeholder], when given,
/// adds a leading `null` entry so "nothing selected" is a real choice.
class LpgDropdownField<T> extends StatelessWidget {
  const LpgDropdownField({
    super.key,
    required this.value,
    required this.items,
    required this.onChanged,
    this.label,
    this.placeholder,
    this.prefixIcon,
    this.validator,
    this.isRequired = false,
  });

  final T value;
  final Map<T, String> items;
  final void Function(T?)? onChanged;
  final String? label;
  final String? placeholder;
  final IconData? prefixIcon;
  final String? Function(T?)? validator;
  final bool isRequired;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;

    final field = DropdownButtonFormField<T>(
      initialValue: value,
      isExpanded: true,
      validator: validator,
      icon: Icon(LpgIcons.chevronDown, color: colors.textSecondary),
      style: context.lpgText.bodyLarge,
      dropdownColor: colors.card,
      borderRadius: BorderRadius.circular(LpgRadius.lg),
      decoration: InputDecoration(
        prefixIcon: prefixIcon == null
            ? null
            : Icon(prefixIcon, size: LpgSizes.iconMd),
      ),
      items: [
        if (placeholder != null)
          DropdownMenuItem<T>(
            value: null,
            child: Text(
              placeholder!,
              style: context.lpgText.bodyLarge?.copyWith(
                color: colors.textDisabled,
              ),
            ),
          ),
        ...items.entries.map(
          (e) => DropdownMenuItem<T>(value: e.key, child: Text(e.value)),
        ),
      ],
      onChanged: onChanged,
    );

    if (label == null) return field;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        LpgFieldLabel(label!, isRequired: isRequired),
        field,
      ],
    );
  }
}
