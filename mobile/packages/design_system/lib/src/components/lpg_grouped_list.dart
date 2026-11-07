import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import 'lpg_card.dart';
import 'lpg_list_tile.dart';

/// The one list look every app uses: a single rounded card, rows divided by
/// full-width hairlines, each row fading in just after the one above
/// it. Fill it with [LpgListTile]s (or a [Column] that starts with one).
///
/// When some rows open a detail screen (a chevron) and others do not, the rows
/// without one keep the chevron's space empty, so their trailing content lines
/// up with the rest. This is worked out from the direct [LpgListTile] children;
/// give a row that is wrapped in another widget `reserveChevronSpace` itself.
///
/// The Customer App's "Recent orders" is the reference; orders, invoices,
/// notifications, deliveries, trips and approvals all read the same.
class LpgGroupedList extends StatelessWidget {
  const LpgGroupedList({
    super.key,
    required this.children,
    this.staggerFrom = 0,
    this.variant = LpgCardVariant.outlined,
  });

  final List<Widget> children;

  /// The stagger index of the first row, so a list further down a screen
  /// continues the entrance of what is above it.
  final int staggerFrom;
  final LpgCardVariant variant;

  @override
  Widget build(BuildContext context) {
    final hasChevron = children.any((c) => c is LpgListTile && c.showChevron);
    final card = _card();
    return hasChevron ? LpgChevronColumn(child: card) : card;
  }

  Widget _card() {
    return LpgCard(
      variant: variant,
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) const Divider(),
            LpgFadeSlideIn(index: staggerFrom + i, child: children[i]),
          ],
        ],
      ),
    );
  }
}
