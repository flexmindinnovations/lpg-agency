import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// The labeled, bordered text field every form in this app needs (order
/// placement, address entry, KYC submission) — wraps `TextFormField` with
/// consistent border/radius/focus-colour theming instead of each screen
/// configuring its own `InputDecoration`.
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
    this.obscureText = false,
    this.maxLines = 1,
    this.enabled = true,
    this.validator,
    this.onChanged,
    this.suffixIcon,
    this.autofocus = false,
  });

  final String label;
  final TextEditingController? controller;
  final String? initialValue;
  final String? hintText;
  final String? errorText;
  final String? helperText;
  final TextInputType? keyboardType;
  final bool obscureText;
  final int maxLines;
  final bool enabled;
  final String? Function(String?)? validator;
  final void Function(String)? onChanged;
  final Widget? suffixIcon;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final radius = BorderRadius.circular(LpgTokens.radiusMd * 1.0);

    OutlineInputBorder border(Color color, {double width = 1}) =>
        OutlineInputBorder(
          borderRadius: radius,
          borderSide: BorderSide(color: color, width: width),
        );

    return TextFormField(
      controller: controller,
      initialValue: controller == null ? initialValue : null,
      keyboardType: keyboardType,
      obscureText: obscureText,
      maxLines: obscureText ? 1 : maxLines,
      enabled: enabled,
      validator: validator,
      onChanged: onChanged,
      autofocus: autofocus,
      style: TextStyle(color: colors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        hintText: hintText,
        errorText: errorText,
        helperText: helperText,
        suffixIcon: suffixIcon,
        filled: true,
        fillColor: colors.surfaceRaised,
        labelStyle: TextStyle(color: colors.textSecondary),
        hintStyle: TextStyle(color: colors.textSecondary),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: LpgTokens.spacingMd * 1.0,
          vertical: LpgTokens.spacingMd * 1.0,
        ),
        border: border(colors.borderDefault),
        enabledBorder: border(colors.borderDefault),
        disabledBorder: border(colors.borderDefault),
        focusedBorder: border(colors.actionPrimary, width: 2),
        errorBorder: border(colors.statusDanger),
        focusedErrorBorder: border(colors.statusDanger, width: 2),
      ),
    );
  }
}
