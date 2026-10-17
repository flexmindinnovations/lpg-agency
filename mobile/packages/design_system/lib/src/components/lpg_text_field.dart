import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../layout.dart';
import '../theme.dart';

/// The label above a form control. Shared by [LpgTextField],
/// [LpgDropdownField] and any custom control a screen builds, so every
/// field in every form is labelled the same way.
class LpgFieldLabel extends StatelessWidget {
  const LpgFieldLabel(this.text, {super.key, this.isRequired = false});

  final String text;

  /// Appends a required marker, announced to screen readers as "required".
  final bool isRequired;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Padding(
      padding: const EdgeInsets.only(
        left: LpgSpacing.xs,
        bottom: LpgSpacing.sm,
      ),
      child: Text.rich(
        TextSpan(
          text: text,
          children: [
            if (isRequired)
              TextSpan(
                text: ' *',
                style: TextStyle(color: colors.statusDanger),
                semanticsLabel: ', required',
              ),
          ],
        ),
        style: context.lpgText.labelLarge?.copyWith(
          color: colors.textSecondary,
        ),
      ),
    );
  }
}

/// The labelled text field every form uses. Wraps `TextFormField`; borders,
/// fill, radius and focus colour all come from `LpgTheme`'s
/// `inputDecorationTheme`, so this widget only adds the label and the
/// options screens actually need.
class LpgTextField extends StatelessWidget {
  const LpgTextField({
    super.key,
    required this.label,
    this.controller,
    this.initialValue,
    this.hintText,
    this.errorText,
    this.helperText,
    this.keyboardType,
    this.textInputAction,
    this.textCapitalization = TextCapitalization.none,
    this.inputFormatters,
    this.obscureText = false,
    this.maxLines = 1,
    this.maxLength,
    this.enabled = true,
    this.readOnly = false,
    this.validator,
    this.onChanged,
    this.onSubmitted,
    this.onTap,
    this.prefixIcon,
    this.prefixText,
    this.suffixIcon,
    this.autofocus = false,
    this.focusNode,
    this.isRequired = false,
    this.autofillHints,
  });

  final String label;
  final TextEditingController? controller;
  final String? initialValue;
  final String? hintText;
  final String? errorText;
  final String? helperText;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final TextCapitalization textCapitalization;
  final List<TextInputFormatter>? inputFormatters;
  final bool obscureText;
  final int maxLines;
  final int? maxLength;
  final bool enabled;
  final bool readOnly;
  final String? Function(String?)? validator;
  final void Function(String)? onChanged;
  final void Function(String)? onSubmitted;
  final VoidCallback? onTap;

  /// Leading icon inside the field, e.g. a phone glyph on a phone field.
  final IconData? prefixIcon;

  /// Fixed leading text inside the field, e.g. `+91 `.
  final String? prefixText;
  final Widget? suffixIcon;
  final bool autofocus;
  final FocusNode? focusNode;
  final bool isRequired;
  final Iterable<String>? autofillHints;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label.isNotEmpty) LpgFieldLabel(label, isRequired: isRequired),
        TextFormField(
          controller: controller,
          initialValue: controller == null ? initialValue : null,
          keyboardType: keyboardType,
          textInputAction: textInputAction,
          textCapitalization: textCapitalization,
          inputFormatters: inputFormatters,
          obscureText: obscureText,
          maxLines: obscureText ? 1 : maxLines,
          maxLength: maxLength,
          enabled: enabled,
          readOnly: readOnly,
          validator: validator,
          onChanged: onChanged,
          onFieldSubmitted: onSubmitted,
          onTap: onTap,
          autofocus: autofocus,
          focusNode: focusNode,
          autofillHints: autofillHints,
          style: context.lpgText.bodyLarge?.copyWith(
            color: enabled ? colors.textPrimary : colors.textSecondary,
          ),
          decoration: InputDecoration(
            hintText: hintText,
            errorText: errorText,
            helperText: helperText,
            prefixText: prefixText,
            prefixIcon: prefixIcon == null
                ? null
                : Icon(prefixIcon, size: LpgSizes.iconMd),
            suffixIcon: suffixIcon,
            fillColor: enabled ? colors.card : colors.surfaceOverlay,
          ),
        ),
      ],
    );
  }
}
