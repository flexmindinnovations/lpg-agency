import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// One live number with a tinted icon, tappable when it has somewhere to go
/// (a chevron shows then). Used by the dashboard's sections.
class MetricTile extends StatelessWidget {
  const MetricTile({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    this.caption,
    this.tone = LpgTone.primary,
    this.onTap,
    this.attention = false,
  });

  final String label;
  final String value;
  final IconData icon;

  /// A smaller line under the label ("3 invoices").
  final String? caption;
  final LpgTone tone;
  final VoidCallback? onTap;

  /// Outlines the tile in its tone: something here needs the owner.
  final bool attention;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final tappable = onTap != null;

    return Semantics(
      button: tappable,
      label: '$label: $value${caption == null ? '' : ', $caption'}',
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(LpgRadius.xl),
          border: attention
              ? Border.all(color: tone.foreground(colors), width: 1.5)
              : null,
        ),
        child: LpgCard(
          onTap: onTap,
          padding: const EdgeInsets.all(LpgSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  LpgIconBox(icon: icon, tone: tone, size: 36),
                  const Spacer(),
                  if (tappable)
                    Icon(
                      LpgIcons.chevronRight,
                      size: LpgSizes.iconSm,
                      color: colors.textSecondary,
                    ),
                ],
              ),
              const SizedBox(height: LpgSpacing.smd),
              Text(
                value,
                style: text.headlineSmall,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: text.bodySmall?.copyWith(color: colors.textSecondary),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              if (caption != null)
                Text(
                  caption!,
                  style: text.labelSmall?.copyWith(
                    color: tone.foreground(colors),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Lays [tiles] out two to a row, equal width, as the dashboard sections do.
class MetricGrid extends StatelessWidget {
  const MetricGrid({super.key, required this.tiles});

  final List<Widget> tiles;

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    for (var i = 0; i < tiles.length; i += 2) {
      rows.add(
        Padding(
          padding: const EdgeInsets.only(bottom: LpgSpacing.md),
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: tiles[i]),
                const SizedBox(width: LpgSpacing.md),
                Expanded(
                  child: i + 1 < tiles.length ? tiles[i + 1] : const SizedBox(),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return Column(children: rows);
  }
}

/// A section heading with an optional "See all" link.
class SectionHeading extends StatelessWidget {
  const SectionHeading(
    this.title, {
    super.key,
    this.actionLabel,
    this.onAction,
    this.topGap = 0,
  });

  final String title;

  /// Space above the heading, for screens that stack sections without gaps.
  final double topGap;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    return Padding(
      padding: EdgeInsets.only(top: topGap, bottom: LpgSpacing.sm),
      child: Row(
        children: [
          Expanded(child: Text(title, style: text.titleMedium)),
          if (onAction != null)
            TextButton(
              onPressed: onAction,
              child: Text(actionLabel ?? 'See all'),
            ),
        ],
      ),
    );
  }
}
