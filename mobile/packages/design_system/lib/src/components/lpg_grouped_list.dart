import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import 'lpg_card.dart';

/// The one list look every app uses: a single rounded card, rows divided by
/// hairlines inset past the icon, each row fading in just after the one above
/// it. Fill it with [LpgListTile]s (or a [Column] that starts with one).
///
/// The Customer App's "Recent orders" is the reference; orders, invoices,
/// notifications, deliveries, trips and approvals all read the same.
class LpgGroupedList extends StatelessWidget {
  const LpgGroupedList({
    super.key,
    required this.children,
    this.staggerFrom = 0,
    this.variant = LpgCardVariant.elevated,
  });

  final List<Widget> children;

  /// The stagger index of the first row, so a list further down a screen
  /// continues the entrance of what is above it.
  final int staggerFrom;
  final LpgCardVariant variant;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      variant: variant,
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) const Divider(indent: LpgSpacing.md),
            LpgFadeSlideIn(index: staggerFrom + i, child: children[i]),
          ],
        ],
      ),
    );
  }
}
