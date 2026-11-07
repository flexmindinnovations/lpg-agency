import 'package:flutter/material.dart';

import '../glass.dart';
import '../icons.dart';
import '../layout.dart';
import '../surface.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_button.dart';

/// Transient and modal feedback, so every screen confirms, warns and asks
/// the same way.
abstract final class LpgFeedback {
  /// A floating snackbar with a tone icon: "Order placed", "Couldn't save".
  /// Replaces any snackbar already showing.
  static void showToast(
    BuildContext context,
    String message, {
    LpgTone tone = LpgTone.neutral,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    final colors = context.lpgColors;
    final IconData? icon = switch (tone) {
      LpgTone.success => LpgIcons.successFilled,
      LpgTone.danger => LpgIcons.error,
      LpgTone.warning => LpgIcons.warning,
      LpgTone.info => LpgIcons.info,
      _ => null,
    };
    // The snackbar sits on a near-black surface in every theme, so the
    // tone colours used are the dark-theme ones (light enough to read).
    final iconColor = colors.isHighContrast
        ? colors.textInverse
        : tone.foreground(LpgTheme.colorsFor(LpgThemeVariant.dark));

    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Row(
            children: [
              if (icon != null) ...[
                Icon(icon, color: iconColor, size: LpgSizes.iconMd),
                const SizedBox(width: LpgSpacing.smd),
              ],
              Expanded(child: Text(message)),
            ],
          ),
          action: actionLabel == null || onAction == null
              ? null
              : SnackBarAction(label: actionLabel, onPressed: onAction),
        ),
      );
  }

  /// A modal bottom sheet of frosted glass (the screen behind it, dimmed, is
  /// blurred through it), with a grab handle, an optional title, and
  /// keyboard-aware padding. High contrast gets a solid sheet.
  static Future<T?> showSheet<T>(
    BuildContext context, {
    required WidgetBuilder builder,
    String? title,
    String? subtitle,
    bool isScrollControlled = true,
  }) {
    const top = BorderRadius.vertical(top: Radius.circular(LpgRadius.xxl));
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: isScrollControlled,
      useSafeArea: true,
      // The sheet below draws its own paper, shape and handle.
      backgroundColor: Colors.transparent,
      elevation: 0,
      showDragHandle: false,
      // Centred, phone-ish width on tablets instead of a full-width slab.
      constraints: const BoxConstraints(maxWidth: 560),
      builder: (sheetContext) => LpgGlass(
        level: LpgSurfaceLevel.sheet,
        radius: top,
        child: Padding(
          padding: EdgeInsets.only(
            left: LpgSpacing.mdl,
            right: LpgSpacing.mdl,
            bottom:
                MediaQuery.viewInsetsOf(sheetContext).bottom + LpgSpacing.lg,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const LpgSheetHandle(),
              if (title != null) ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Semantics(
                            header: true,
                            child: Text(
                              title,
                              style: sheetContext.lpgText.titleLarge,
                            ),
                          ),
                          if (subtitle != null) ...[
                            const SizedBox(height: LpgSpacing.xs),
                            Text(
                              subtitle,
                              style: sheetContext.lpgText.bodyMedium?.copyWith(
                                color: sheetContext.lpgColors.textSecondary,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    // A visible way out, for people who do not discover the
                    // drag handle or a tap on the scrim.
                    IconButton(
                      tooltip: 'Close',
                      onPressed: () => Navigator.of(sheetContext).maybePop(),
                      icon: const Icon(LpgIcons.close),
                    ),
                  ],
                ),
                const SizedBox(height: LpgSpacing.sm),
              ],
              Flexible(child: builder(sheetContext)),
            ],
          ),
        ),
      ),
    );
  }

  /// A yes/no confirmation. Resolves `true` only when the user confirms.
  /// [destructive] colours the confirm button as danger.
  static Future<bool> confirm(
    BuildContext context, {
    required String title,
    required String message,
    String confirmLabel = 'Confirm',
    String cancelLabel = 'Cancel',
    bool destructive = false,
  }) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actionsPadding: const EdgeInsets.fromLTRB(
          LpgSpacing.lg,
          0,
          LpgSpacing.lg,
          LpgSpacing.lg,
        ),
        actions: [
          LpgButton(
            label: cancelLabel,
            variant: LpgButtonVariant.text,
            onPressed: () => Navigator.of(dialogContext).pop(false),
          ),
          LpgButton(
            label: confirmLabel,
            variant: destructive
                ? LpgButtonVariant.destructive
                : LpgButtonVariant.primary,
            onPressed: () => Navigator.of(dialogContext).pop(true),
          ),
        ],
      ),
    );
    return result ?? false;
  }
}
