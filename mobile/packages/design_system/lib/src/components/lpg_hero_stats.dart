import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// One figure and its label in an [LpgHeroStats] strip.
class LpgHeroStat {
  const LpgHeroStat({required this.value, required this.label});

  final String value;
  final String label;
}

/// A row of two to four figures for the bottom of an [LpgHeroCard], each in
/// its own column with a thin solid divider between them. Replaces a long
/// "3 delivered • 0 failed • 2 to approve" sentence: each figure reads at a
/// glance and the label wraps under its own number.
///
/// Draws in the hero's own colours, so it belongs inside a hero card only.
class LpgHeroStats extends StatelessWidget {
  LpgHeroStats({super.key, required this.stats})
    : assert(stats.length >= 2 && stats.length <= 4);

  final List<LpgHeroStat> stats;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final figure = (text.titleLarge ?? const TextStyle()).copyWith(
      color: colors.onHero,
      fontWeight: FontWeight.w800,
      fontFeatures: const [FontFeature.tabularFigures()],
    );

    final cells = <Widget>[];
    for (var i = 0; i < stats.length; i++) {
      if (i > 0) {
        cells.add(
          ExcludeSemantics(
            child: Container(
              width: 1,
              margin: const EdgeInsets.symmetric(horizontal: LpgSpacing.sm),
              color: colors.heroTrack,
            ),
          ),
        );
      }
      cells.add(
        Expanded(
          child: Semantics(
            label: [stats[i].label, stats[i].value].join(': '),
            excludeSemantics: true,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(stats[i].value, style: figure),
                Text(
                  stats[i].label,
                  style: text.bodySmall?.copyWith(color: colors.heroMuted),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return IntrinsicHeight(child: Row(children: cells));
  }
}
