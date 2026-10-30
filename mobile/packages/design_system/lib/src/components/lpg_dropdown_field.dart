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
/// adds a leading `null` entry so "nothing selected" is a real choice. A
/// [value] that is not among [items] counts as "nothing selected".
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

    // A value that is not one of the items (a screen's "nothing chosen yet"
    // sentinel such as '') shows the placeholder instead of failing
    // Flutter's "exactly one item with this value" assertion.
    final field = DropdownButtonFormField<T>(
      initialValue: items.containsKey(value) ? value : null,
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
          (e) => DropdownMenuItem<T>(
            value: e.key,
            child: Text(e.value, maxLines: 2, overflow: TextOverflow.ellipsis),
          ),
        ),
      ],
      // The closed field shows one line that ends in an ellipsis, so a long
      // address never looks cut off mid-word (CA-14); the open menu above
      // allows two lines so the options stay distinguishable.
      selectedItemBuilder: (context) => [
        if (placeholder != null)
          Text(
            placeholder!,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: context.lpgText.bodyLarge?.copyWith(
              color: colors.textDisabled,
            ),
          ),
        for (final label in items.values)
          Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
      ],
      onChanged: onChanged,
    );

    if (label == null) return field;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        ExcludeSemantics(child: LpgFieldLabel(label!, isRequired: isRequired)),
        Semantics(
          label: isRequired ? '${label!}, required' : label,
          child: field,
        ),
      ],
    );
  }
}
