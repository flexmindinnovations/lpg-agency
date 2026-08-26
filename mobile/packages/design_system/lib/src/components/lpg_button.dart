import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// Visual weight of an [LpgButton] — primary for the one action a screen
/// wants taken, secondary for anything else that still needs a button
/// shape, text for the lowest-emphasis inline action.
enum LpgButtonVariant { primary, secondary, text }

/// The pill-shaped button every screen in this app should use instead of a
/// raw `ElevatedButton` — `dashboard_screen.dart` and `order_bottom_sheet
/// .dart` each hand-built their own before this existed. Reuses the same
/// `ElevatedButtonTheme`/`StadiumBorder` shape `LpgTheme` already
/// configures, so a bare `ElevatedButton` and this still look identical —
/// the point of this widget is the loading state, icon slot and variant
/// switch, not a new visual language.
class LpgButton extends StatelessWidget {
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

  /// Stretches to the parent's full width — the common case for a primary
  /// action at the bottom of a form or sheet.
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final disabled = onPressed == null || isLoading;

    final child = isLoading
        ? SizedBox(
            width: LpgTokens.typographyBodyFontSize.toDouble(),
            height: LpgTokens.typographyBodyFontSize.toDouble(),
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(
                variant == LpgButtonVariant.primary
                    ? colors.textInverse
                    : colors.actionPrimary,
              ),
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 18),
                const SizedBox(width: LpgTokens.spacingSm * 1.0),
              ],
              Text(label),
            ],
          );

    final Widget button = switch (variant) {
      LpgButtonVariant.primary => ElevatedButton(
        onPressed: disabled ? null : onPressed,
        child: child,
      ),
      LpgButtonVariant.secondary => OutlinedButton(
        onPressed: disabled ? null : onPressed,
        style: OutlinedButton.styleFrom(
          foregroundColor: colors.textPrimary,
          side: BorderSide(color: colors.borderStrong),
          shape: const StadiumBorder(),
          padding: const EdgeInsets.symmetric(
            horizontal: LpgTokens.spacingLg * 1.0,
            vertical: LpgTokens.spacingMd * 1.0,
          ),
          textStyle: const TextStyle(
            fontSize: LpgTokens.typographyBodyFontSize * 1.0,
            fontWeight: FontWeight.w600,
          ),
        ),
        child: child,
      ),
      LpgButtonVariant.text => TextButton(
        onPressed: disabled ? null : onPressed,
        style: TextButton.styleFrom(
          foregroundColor: colors.actionPrimary,
          textStyle: const TextStyle(
            fontSize: LpgTokens.typographyBodyFontSize * 1.0,
            fontWeight: FontWeight.w600,
          ),
        ),
        child: child,
      ),
    };

    return expand ? SizedBox(width: double.infinity, child: button) : button;
  }
}
