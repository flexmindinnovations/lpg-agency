import 'package:flutter/material.dart';

import 'theme.dart';

/// The colour role a decorative element takes: the tinted square behind a
/// list-row icon, a stat tile, a banner, a quick action.
///
/// A superset of [LpgStatusSeverity]'s status roles plus the two brand roles,
/// so one enum drives every tonal surface and screens never pick a raw
/// colour for "this one should look like a warning".
enum LpgTone { primary, accent, success, warning, danger, info, neutral }

extension LpgToneColors on LpgTone {
  /// The tone's strong colour: icon, text, or border.
  Color foreground(LpgColors colors) => switch (this) {
    LpgTone.primary =>
      colors.isHighContrast
          ? colors.actionPrimary
          : colors.onActionPrimaryContainer,
    LpgTone.accent => colors.accent,
    LpgTone.success => colors.statusSuccess,
    LpgTone.warning => colors.statusWarning,
    LpgTone.danger => colors.statusDanger,
    LpgTone.info => colors.statusInfo,
    LpgTone.neutral => colors.textSecondary,
  };

  /// The tone's quiet fill, behind [foreground]. High contrast keeps fills
  /// plain (the border carries the tone instead) so text contrast never
  /// depends on a tint.
  Color container(LpgColors colors) {
    if (colors.isHighContrast) return colors.card;
    return switch (this) {
      LpgTone.primary => colors.actionPrimaryContainer,
      LpgTone.neutral => colors.surfaceOverlay,
      _ => foreground(colors).withValues(alpha: 0.12),
    };
  }
}
