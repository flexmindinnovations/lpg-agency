import 'package:flutter/material.dart';

import '../layout.dart';

/// Two or more buttons side by side, right aligned with one standard gap.
///
/// Put the quiet or destructive action first and the main one last, so the
/// main action is always the one at the right edge. At large text sizes, when
/// the buttons no longer fit on one line, the last ones wrap onto the next
/// line, still right aligned. Use it for pages and cards; a form sheet uses
/// `LpgSheetActions`, which pins full-width buttons instead.
class LpgActionRow extends StatelessWidget {
  const LpgActionRow({super.key, required this.children});

  /// The buttons, in reading order: the main action last.
  final List<Widget> children;

  /// The space between buttons, on the same line and between lines.
  static const double gap = LpgSpacing.smd;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: AlignmentDirectional.centerEnd,
      heightFactor: 1,
      child: Wrap(
        alignment: WrapAlignment.end,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: gap,
        runSpacing: gap,
        children: children,
      ),
    );
  }
}
