import 'package:flutter/material.dart';

import '../layout.dart';
import 'lpg_button.dart';

/// Two or more buttons side by side, with one standard gap.
///
/// The default row is right aligned, each button as wide as its label: put the
/// quiet or destructive action first and the main one last, so the main action
/// is always the one at the right edge. At large text sizes, when the buttons
/// no longer fit on one line, the last ones wrap onto the next line, still
/// right aligned. Use it for pages and cards; a form sheet uses
/// `LpgSheetActions`, which pins full-width buttons instead.
///
/// [LpgActionRow.equal] is for a decision between two or three choices that
/// carry the same weight (Dispute or Accept): the buttons share the row in
/// equal parts. At large text sizes the parts would be too narrow to read, so
/// the buttons stack instead, each the full width, in the same order.
class LpgActionRow extends StatelessWidget {
  const LpgActionRow({super.key, required this.children}) : equal = false;

  /// Buttons that share the row in equal widths (see the class comment).
  const LpgActionRow.equal({super.key, required this.children}) : equal = true;

  /// The buttons, in reading order: the main action last.
  final List<Widget> children;

  /// Whether the buttons share the row in equal parts.
  final bool equal;

  /// The space between buttons, on the same line and between lines.
  static const double gap = LpgSpacing.smd;

  /// Above this text scale the equal parts are too narrow, so they stack.
  static const double stackAboveTextScale = 1.3;

  @override
  Widget build(BuildContext context) {
    if (equal) {
      return LpgButtonExpansion(child: _equalParts(context));
    }
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

  Widget _equalParts(BuildContext context) {
    final scale = MediaQuery.textScalerOf(context).scale(16) / 16;
    if (scale > stackAboveTextScale) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) const SizedBox(height: gap),
            children[i],
          ],
        ],
      );
    }
    return Row(
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) const SizedBox(width: gap),
          Expanded(child: children[i]),
        ],
      ],
    );
  }
}
