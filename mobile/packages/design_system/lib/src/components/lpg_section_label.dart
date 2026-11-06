import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// The small bold heading above a group ("CUSTOMERS AND BILLING"): capitals in
/// the main text colour. It replaces a grey, light label that was hard to read
/// on a see-through card page.
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
    );
  }
}
