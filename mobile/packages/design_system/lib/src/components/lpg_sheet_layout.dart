import 'package:flutter/material.dart';

import '../layout.dart';
import 'lpg_banner.dart';
import 'lpg_button.dart';
import '../tone.dart';

/// The body of a form sheet: the fields scroll, the [footer] stays put.
///
/// A sheet with a keyboard open can be shorter than its form. With the
/// button inside the scroll view the person has to scroll to find it, and an
/// error shown below it is out of sight; pinning the footer keeps both in
/// view. Use it as what the `builder` of `LpgFeedback.showSheet` returns.
class LpgSheetLayout extends StatelessWidget {
  const LpgSheetLayout({super.key, required this.body, this.footer});

  /// The fields and explanation; scrolls when it does not fit.
  final Widget body;

  /// Pinned below the body, usually an [LpgSheetActions].
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Flexible(child: SingleChildScrollView(child: body)),
        if (footer != null) ...[const SizedBox(height: LpgSpacing.md), footer!],
      ],
    );
  }
}

/// The pinned actions of a form sheet: an optional error banner, one full
/// width primary button, and an optional second button for the alternative
/// ("Cancel", "Skip", "Reject", "Back").
///
/// The second button is a quiet text button by default; give it
/// [secondaryVariant] `secondary` when it is a real decision of equal weight
/// (Accept / Reject). While either button is loading, both are disabled.
class LpgSheetActions extends StatelessWidget {
  const LpgSheetActions({
    super.key,
    required this.primaryLabel,
    required this.onPrimary,
    this.primaryIcon,
    this.primaryVariant = LpgButtonVariant.primary,
    this.isLoading = false,
    this.secondaryLabel,
    this.onSecondary,
    this.secondaryIcon,
    this.secondaryVariant = LpgButtonVariant.text,
    this.isSecondaryLoading = false,
    this.error,
  });

  final String primaryLabel;

  /// Null disables the button (nothing to submit yet, or busy).
  final VoidCallback? onPrimary;
  final IconData? primaryIcon;
  final LpgButtonVariant primaryVariant;

  /// The primary button is working.
  final bool isLoading;
  final String? secondaryLabel;
  final VoidCallback? onSecondary;
  final IconData? secondaryIcon;
  final LpgButtonVariant secondaryVariant;

  /// The second button is working (a sheet with two decisions).
  final bool isSecondaryLoading;

  /// Shown above the buttons as a danger banner, so it is never scrolled out
  /// of sight.
  final String? error;

  @override
  Widget build(BuildContext context) {
    final busy = isLoading || isSecondaryLoading;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (error != null) ...[
          LpgBanner(tone: LpgTone.danger, message: error!),
          const SizedBox(height: LpgSpacing.sm),
        ],
        LpgButton(
          label: primaryLabel,
          icon: primaryIcon,
          variant: primaryVariant,
          isLoading: isLoading,
          expand: true,
          onPressed: busy ? null : onPrimary,
        ),
        if (secondaryLabel != null) ...[
          SizedBox(
            height: secondaryVariant == LpgButtonVariant.text
                ? LpgSpacing.xs
                : LpgSpacing.sm,
          ),
          LpgButton(
            label: secondaryLabel!,
            icon: secondaryIcon,
            variant: secondaryVariant,
            isLoading: isSecondaryLoading,
            expand: true,
            onPressed: busy ? null : onSecondary,
          ),
        ],
      ],
    );
  }
}
