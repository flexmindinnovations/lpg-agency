import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// The small bold heading above a group ("CUSTOMERS AND BILLING"): capitals in
/// the main text colour, led by the same short accent bar as
/// `LpgSectionHeader`. It replaces a grey, light label that was hard to read on
/// a see-through card page.
class LpgSectionLabel extends StatelessWidget {
  const LpgSectionLabel(
    this.label, {
    super.key,
    this.padding = const EdgeInsets.only(
      top: LpgSpacing.md,
      bottom: LpgSpacing.smd,
    ),
  });

  final String label;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Padding(
      padding: padding,
      child: Row(
        children: [
          const LpgAccentBar(height: 16),
          const SizedBox(width: LpgSpacing.sm),
          Expanded(
            child: Semantics(
              header: true,
              child: Text(
                label.toUpperCase(),
                style: context.lpgText.labelLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1,
                  color: colors.textPrimary,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The short rounded bar that leads a section heading, in the primary action
/// colour. Decoration only, so a screen reader skips it.
class LpgAccentBar extends StatelessWidget {
  const LpgAccentBar({super.key, this.height = 20});

  final double height;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
        width: 4,
        height: height,
        decoration: BoxDecoration(
          color: context.lpgColors.actionPrimary,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
