import 'package:flutter/widgets.dart';

import 'tokens.dart';

/// Spacing scale as `double`s, straight from the generated spacing tokens.
///
/// The generated tokens are `int`s (they are shared with CSS, where `16`
/// becomes `16px`); every Flutter layout API wants a `double`. This is the one
/// place that conversion happens, so screens write `LpgSpacing.md` instead of
/// `LpgTokens.spacingMd * 1.0` or, worse, a bare `16`.
abstract final class LpgSpacing {
  static const double none = LpgTokens.spacingNone * 1.0;
  static const double xs = LpgTokens.spacingXs * 1.0;
  static const double sm = LpgTokens.spacingSm * 1.0;

  /// Between [sm] and [md]: the gap inside compact rows (icon to label,
  /// badge to text). Derived from the token scale, not a new magic number.
  static const double smd = (LpgTokens.spacingSm + LpgTokens.spacingXs) * 1.0;
  static const double md = LpgTokens.spacingMd * 1.0;

  /// Between [md] and [lg]: the default page gutter on phones.
  static const double mdl = (LpgTokens.spacingMd + LpgTokens.spacingXs) * 1.0;
  static const double lg = LpgTokens.spacingLg * 1.0;
  static const double xl = LpgTokens.spacingXl * 1.0;
  static const double xxl = LpgTokens.spacing2xl * 1.0;

  /// Horizontal padding every scrolling page uses, so content edges line up
  /// from screen to screen.
  static const EdgeInsets page = EdgeInsets.fromLTRB(mdl, md, mdl, xl);
}

/// Corner radii, from the generated radius tokens, plus the two larger
/// shapes the mobile apps use for cards and sheets.
abstract final class LpgRadius {
  static const double sm = LpgTokens.radiusSm * 1.0;
  static const double md = LpgTokens.radiusMd * 1.0;
  static const double lg = LpgTokens.radiusLg * 1.0;

  /// Cards, hero panels, quick-action tiles.
  static const double xl = LpgTokens.radiusLg * 1.5;

  /// Bottom sheets and dialogs.
  static const double xxl = LpgTokens.radiusLg * 2.0;
  static const double full = LpgTokens.radiusFull * 1.0;

  static const BorderRadius cardRadius = BorderRadius.all(Radius.circular(xl));
}

/// Fixed component sizes. Touch targets follow WCAG 2.2's 24px minimum with
/// Material's 48px recommendation as the floor we actually ship.
abstract final class LpgSizes {
  static const double touchTarget = LpgTokens.spacing2xl * 1.0;
  static const double iconSm = LpgTokens.spacingMd * 1.0;
  static const double iconMd =
      (LpgTokens.spacingMd + LpgTokens.spacingXs) * 1.0;
  static const double iconLg = LpgTokens.spacingLg * 1.0;
  static const double iconXl = LpgTokens.spacingXl * 1.0;

  /// The tonal square behind a list-row or stat icon.
  static const double iconBox =
      (LpgTokens.spacingXl + LpgTokens.spacingSm) * 1.0;
  static const double avatarSm = LpgTokens.spacingXl * 1.0;
  static const double avatarMd =
      (LpgTokens.spacingXl + LpgTokens.spacingMd) * 1.0;
  static const double avatarLg =
      (LpgTokens.spacing2xl + LpgTokens.spacingMd) * 1.0;
  static const double buttonHeight =
      (LpgTokens.spacing2xl + LpgTokens.spacingSm) * 1.0;
}

/// Window-size breakpoints, from Material 3's window size classes. Phones
/// are "compact"; a tablet (or a phone in landscape) is "medium" or wider,
/// where the apps switch the bottom bar for a navigation rail and cap
/// content width so cards and key/value rows don't stretch edge to edge.
abstract final class LpgBreakpoints {
  /// Below this width is a phone layout.
  static const double medium = 600;

  /// The widest a column of cards and forms is allowed to grow: wide enough
  /// for two-column key/value rows to stay readable, narrow enough that a
  /// label and its value never sit a whole tablet-width apart.
  static const double contentMaxWidth = 720;

  /// The widest a single short form (sign-in) grows: phone-width, centred.
  static const double formMaxWidth = 480;

  /// Whether [context] is wider than a phone.
  static bool isWide(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= medium;
}
