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
/// width primary button, and an optional text button for the alternative
/// ("Cancel", "Skip").
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
    this.error,
  });

  final String primaryLabel;

  /// Null disables the button (nothing to submit yet, or busy).
  final VoidCallback? onPrimary;
  final IconData? primaryIcon;
  final LpgButtonVariant primaryVariant;
  final bool isLoading;
  final String? secondaryLabel;
  final VoidCallback? onSecondary;

  /// Shown above the buttons as a danger banner, so it is never scrolled out
  /// of sight.
  final String? error;

  @override
  Widget build(BuildContext context) {
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
          onPressed: isLoading ? null : onPrimary,
        ),
        if (secondaryLabel != null) ...[
          const SizedBox(height: LpgSpacing.xs),
          LpgButton(
            label: secondaryLabel!,
            variant: LpgButtonVariant.text,
            expand: true,
            onPressed: isLoading ? null : onSecondary,
          ),
        ],
      ],
    );
  }
}
