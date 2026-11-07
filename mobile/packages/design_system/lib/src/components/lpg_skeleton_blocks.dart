import 'package:flutter/material.dart';

import '../glass.dart';
import '../layout.dart';
import '../theme.dart';
import 'lpg_skeleton.dart';

/// Placeholder shapes that match the real layouts, so nothing jumps when the
/// content arrives. Put them inside one [LpgSkeletonGroup]: it is one shimmer
/// for the whole group, not one per block.
class LpgSkeletonGroup extends StatelessWidget {
  const LpgSkeletonGroup({
    super.key,
    required this.children,
    this.gap = LpgSpacing.md,
  });

  final List<Widget> children;

  /// Space between the blocks.
  final double gap;

  @override
  Widget build(BuildContext context) => LpgShimmer(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) SizedBox(height: gap),
          children[i],
        ],
      ],
    ),
  );
}

/// The big solid panel at the top of a home screen ([LpgHeroCard]'s shape).
class LpgSkeletonHero extends StatelessWidget {
  const LpgSkeletonHero({super.key, this.height = 140});

  final double height;

  @override
  Widget build(BuildContext context) =>
      LpgSkeleton(height: height, radius: LpgRadius.xxl);
}

/// A grid of stat tiles ([LpgStatTile]'s shape): [columns] across, [rows]
/// down.
class LpgSkeletonTileGrid extends StatelessWidget {
  const LpgSkeletonTileGrid({
    super.key,
    this.columns = 2,
    this.rows = 2,
    this.tileHeight = 96,
  });

  final int columns;
  final int rows;
  final double tileHeight;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      for (var r = 0; r < rows; r++) ...[
        if (r > 0) const SizedBox(height: LpgSpacing.smd),
        Row(
          children: [
            for (var c = 0; c < columns; c++) ...[
              if (c > 0) const SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: LpgSkeleton(height: tileHeight, radius: LpgRadius.xl),
              ),
            ],
          ],
        ),
      ],
    ],
  );
}

/// A card with [lines] rows of text, for a summary or detail block.
class LpgSkeletonCard extends StatelessWidget {
  const LpgSkeletonCard({super.key, this.lines = 3});

  final int lines;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Container(
      padding: const EdgeInsets.all(LpgSpacing.mdl),
      decoration: BoxDecoration(
        color: colors.cardGlass,
        borderRadius: LpgRadius.cardRadius,
        border: Border.all(color: colors.borderDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < lines; i++) ...[
            if (i > 0) const SizedBox(height: LpgSpacing.sm),
            LpgSkeleton(
              // The last line is shorter, as text ends.
              width: i == lines - 1 ? 120 : null,
              height: LpgSpacing.smd,
            ),
          ],
        ],
      ),
    );
  }
}
