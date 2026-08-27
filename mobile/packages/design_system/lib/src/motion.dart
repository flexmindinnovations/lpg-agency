import 'package:flutter/material.dart';

import 'tokens.dart';

/// Motion tokens following Material 3 Expressive's physics-based model:
/// springs (stiffness/damping) for the interactions that should feel
/// "alive," paired curves for everything animated via a plain [Curve]
/// (`AnimatedContainer`, implicit animations) where a full physics
/// simulation isn't the right tool.
///
/// Every duration comes from the generated `LpgTokens.motionDuration*`
/// tokens (shared with the web app) rather than a value invented here —
/// this file only adds the Flutter-side curve/spring half, which isn't
/// something a CSS token can express. [resolve]/[micro]/[small]/[medium]/
/// [large] also wire up the previously-unused `motionReducedMotionDuration*`
/// tokens: every duration collapses toward zero when the platform's
/// reduce-motion accessibility setting is on
/// (`MediaQuery.disableAnimations`), which nothing in this package
/// respected before.
abstract final class LpgMotion {
  /// M3 Expressive's "spatial spring" — for elements that move or resize
  /// in space (press feedback, card entrance, dialogs): underdamped, so it
  /// visibly overshoots and settles, mirroring physical momentum rather
  /// than easing to a stop.
  static const spatialSpring = SpringDescription(
    mass: 1,
    stiffness: 500,
    damping: 20,
  );

  /// M3 Expressive's "effects spring" as a [Curve] — for colour/opacity/
  /// elevation changes on implicit animations: fast, no overshoot, settles
  /// cleanly. (Effects changes in M3 Expressive are still spring-driven in
  /// spec; approximated here as a curve because `AnimatedContainer`/
  /// `AnimatedOpacity` etc. take a [Curve], not a [SpringDescription].)
  static const effectsCurve = Curves.easeOutCubic;

  /// [spatialSpring] approximated as a [Curve], for the same reason —
  /// visible controlled overshoot on a plain implicit animation.
  static const spatialCurve = Curves.easeOutBack;

  /// Returns [reduced] when the platform's reduce-motion setting is on,
  /// [normal] otherwise.
  static Duration resolve(
    BuildContext context, {
    required Duration normal,
    required Duration reduced,
  }) => (MediaQuery.maybeOf(context)?.disableAnimations ?? false)
      ? reduced
      : normal;

  static Duration micro(BuildContext context) => resolve(
    context,
    normal: LpgTokens.motionDurationMicro,
    reduced: LpgTokens.motionReducedMotionDurationMicro,
  );

  static Duration small(BuildContext context) => resolve(
    context,
    normal: LpgTokens.motionDurationSmall,
    reduced: LpgTokens.motionReducedMotionDurationSmall,
  );

  static Duration medium(BuildContext context) => resolve(
    context,
    normal: LpgTokens.motionDurationMedium,
    reduced: LpgTokens.motionReducedMotionDurationMedium,
  );

  static Duration large(BuildContext context) => resolve(
    context,
    normal: LpgTokens.motionDurationLarge,
    reduced: LpgTokens.motionReducedMotionDurationLarge,
  );
}
