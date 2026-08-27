import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// Visual weight of an [LpgButton] — primary for the one action a screen
/// wants taken, secondary for anything else that still needs a button
/// shape, text for the lowest-emphasis inline action.
enum LpgButtonVariant { primary, secondary, text }

/// A tactile, modern button following skeuomorphic (Neumorphic) principles.
/// Replaces the flat Material 3 buttons with physical-feeling surfaces.
class LpgButton extends StatefulWidget {
  const LpgButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = LpgButtonVariant.primary,
    this.icon,
    this.isLoading = false,
    this.expand = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final LpgButtonVariant variant;
  final IconData? icon;
  final bool isLoading;

  /// Stretches to the parent's full width.
  final bool expand;

  @override
  State<LpgButton> createState() => _LpgButtonState();
}

class _LpgButtonState extends State<LpgButton> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final disabled = widget.onPressed == null || widget.isLoading;

    final isHighContrast =
        theme.brightness == Brightness.light &&
        colors.shadowLight == Colors.transparent;

    if (widget.variant == LpgButtonVariant.text || isHighContrast) {
      return _buildFlatButton(context, colors, theme, disabled);
    }

    final baseColor = widget.variant == LpgButtonVariant.primary
        ? colors.actionPrimary
        : colors.surfaceBase;

    final textColor = widget.variant == LpgButtonVariant.primary
        ? colors.textInverse
        : colors.textPrimary;

    Widget content = widget.isLoading
        ? SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(textColor),
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.icon != null) ...[
                Icon(widget.icon, size: 18, color: textColor),
                const SizedBox(width: LpgTokens.spacingSm * 1.0),
              ],
              Text(
                widget.label,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: textColor,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          );

    return GestureDetector(
      onTapDown: disabled ? null : (_) => setState(() => _isPressed = true),
      onTapUp: disabled ? null : (_) => setState(() => _isPressed = false),
      onTapCancel: disabled ? null : () => setState(() => _isPressed = false),
      onTap: disabled ? null : widget.onPressed,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 100),
        width: widget.expand ? double.infinity : null,
        padding: const EdgeInsets.symmetric(
          horizontal: LpgTokens.spacingLg * 1.0,
          vertical: LpgTokens.spacingMd * 1.0,
        ),
        decoration: BoxDecoration(
          color: baseColor,
          borderRadius: BorderRadius.circular(LpgTokens.radiusFull * 1.0),
          boxShadow: _isPressed || disabled
              ? null
              : [
                  BoxShadow(
                    color: colors.shadowLight,
                    offset: const Offset(-3, -3),
                    blurRadius: 8,
                  ),
                  BoxShadow(
                    color: colors.shadowDark,
                    offset: const Offset(3, 3),
                    blurRadius: 8,
                  ),
                ],
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: _isPressed
                ? [baseColor.withValues(alpha: 0.9), baseColor]
                : [baseColor, baseColor.withValues(alpha: 0.95)],
          ),
        ),
        child: Opacity(opacity: disabled ? 0.6 : 1.0, child: content),
      ),
    );
  }

  Widget _buildFlatButton(
    BuildContext context,
    LpgColors colors,
    ThemeData theme,
    bool disabled,
  ) {
    final child = widget.isLoading
        ? const SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.icon != null) ...[
                Icon(widget.icon, size: 18),
                const SizedBox(width: LpgTokens.spacingSm * 1.0),
              ],
              Text(widget.label),
            ],
          );

    final Widget button = switch (widget.variant) {
      LpgButtonVariant.primary => ElevatedButton(
        onPressed: disabled ? null : widget.onPressed,
        child: child,
      ),
      LpgButtonVariant.secondary => OutlinedButton(
        onPressed: disabled ? null : widget.onPressed,
        child: child,
      ),
      LpgButtonVariant.text => TextButton(
        onPressed: disabled ? null : widget.onPressed,
        child: child,
      ),
    };

    return widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}
