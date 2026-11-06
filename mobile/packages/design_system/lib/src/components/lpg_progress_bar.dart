import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// A thin bar showing how far along something is ("3 of 7 stops done").
///
/// The unfilled track is a clear grey (the secondary text colour at a quarter
/// strength) rather than the hairline colour, so on a see-through card the
/// bar is still seen as a bar and the filled part stands out from it by at
/// least 3:1 (WCAG 1.4.11). Use it on cards and lists; a bar inside a hero
/// uses the hero's own colours.
class LpgProgressBar extends StatelessWidget {
  const LpgProgressBar({super.key, required this.value, this.semanticsLabel});

  /// 0 to 1.
  final double value;

  /// Announced with the percentage, for example "Trip progress".
  final String? semanticsLabel;

  static const height = 8.0;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final track = colors.tint(colors.textSecondary, 0.25, over: colors.card);
    return ClipRRect(
      borderRadius: BorderRadius.circular(LpgRadius.full),
      child: LinearProgressIndicator(
        value: value.clamp(0.0, 1.0),
        minHeight: height,
        backgroundColor: track,
        valueColor: AlwaysStoppedAnimation<Color>(colors.actionPrimary),
        semanticsLabel: semanticsLabel,
        semanticsValue: '${(value.clamp(0.0, 1.0) * 100).round()}%',
      ),
    );
  }
}
