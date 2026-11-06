import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';

/// The label above a form control. Shared by [LpgTextField],
/// [LpgDropdownField] and any custom control a screen builds, so every
/// field in every form is labelled the same way.
class LpgFieldLabel extends StatelessWidget {
  const LpgFieldLabel(
    this.text, {
    super.key,
    this.isRequired = false,
    this.hasError = false,
  });

  final String text;
  final bool isRequired;
  final bool hasError;

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
          color: hasError ? colors.statusDanger : colors.textSecondary,
        ),
      ),
    );
  }
}

/// The labelled text field every form uses. Wraps `TextFormField`; borders,
/// fill, radius and focus colour all come from `LpgTheme`'s
/// `inputDecorationTheme`, so this widget only adds the label and the
/// options screens actually need.
class LpgTextField extends StatefulWidget {
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
  State<LpgTextField> createState() => _LpgTextFieldState();
}

class _LpgTextFieldState extends State<LpgTextField> {
  final GlobalKey<FormFieldState<String>> _fieldKey = GlobalKey();

  void _handleChange() {
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    widget.controller?.addListener(_handleChange);
  }

  @override
  void didUpdateWidget(LpgTextField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller?.removeListener(_handleChange);
      widget.controller?.addListener(_handleChange);
    }
  }

  @override
  void dispose() {
    widget.controller?.removeListener(_handleChange);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final hasError =
        _fieldKey.currentState?.hasError ?? widget.errorText != null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (widget.label.isNotEmpty)
          ExcludeSemantics(
            child: LpgFieldLabel(
              widget.label,
              isRequired: widget.isRequired,
              hasError: hasError,
            ),
          ),
        Semantics(
          label: widget.label.isEmpty
              ? null
              : (widget.isRequired
                    ? '${widget.label}, required'
                    : widget.label),
          child: TextFormField(
            key: _fieldKey,
            controller: widget.controller,
            initialValue: widget.controller == null
                ? widget.initialValue
                : null,
            keyboardType: widget.keyboardType,
            textInputAction: widget.textInputAction,
            textCapitalization: widget.textCapitalization,
            inputFormatters: widget.inputFormatters,
            obscureText: widget.obscureText,
            maxLines: widget.obscureText ? 1 : widget.maxLines,
            maxLength: widget.maxLength,
            enabled: widget.enabled,
            readOnly: widget.readOnly,
            validator: (value) {
              final error = widget.validator?.call(value);
              // Defer state update until after build to refresh the label color
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) setState(() {});
              });
              return error;
            },
            onChanged: (val) {
              if (hasError) _fieldKey.currentState?.validate();
              widget.onChanged?.call(val);
            },
            onFieldSubmitted: widget.onSubmitted,
            onTap: widget.onTap,
            autofocus: widget.autofocus,
            focusNode: widget.focusNode,
            autofillHints: widget.autofillHints,
            style: context.lpgText.bodyLarge?.copyWith(
              color: widget.enabled ? colors.textPrimary : colors.textSecondary,
            ),
            decoration: InputDecoration(
              hintText: widget.hintText,
              errorText: widget.errorText,
              helperText: widget.helperText,
              prefixText: widget.prefixText,
              prefixIcon: widget.prefixIcon == null
                  ? null
                  : Icon(widget.prefixIcon, size: LpgSizes.iconMd),
              suffixIcon:
                  widget.suffixIcon ??
                  (hasError
                      ? Icon(
                          LpgIcons.error,
                          color: colors.statusDanger,
                          size: LpgSizes.iconMd,
                        )
                      : null),
              fillColor: widget.enabled ? colors.card : colors.surfaceOverlay,
            ),
          ),
        ),
      ],
    );
  }
}
