import 'package:flutter/material.dart';
import 'package:flutter/physics.dart' show SpringSimulation;

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

  /// One sweep of a loading shimmer. Deliberately slow: a calm sweep reads
  /// as "loading", a fast one as "flashing".
  static const shimmer = Duration(milliseconds: 1400);

  /// One breath of the "current step" pulse on a timeline, and how many
  /// breaths it takes before resting.
  static const pulse = Duration(milliseconds: 1600);
  static const pulseRepeats = 3;

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

/// Fades and slides its child up into place once, when first built — the
/// entrance every list row, card and section uses so a screen assembles
/// itself rather than popping in.
///
/// [index] staggers siblings: each one starts a beat after the previous,
/// capped so a long list never makes the last row wait. The delay lives
/// inside a single [AnimationController] (as an [Interval]) instead of a
/// `Future.delayed`, so there is never a pending timer for tests or a
/// disposed widget to trip over. Under reduce-motion it renders the child
/// immediately.
class LpgFadeSlideIn extends StatefulWidget {
  const LpgFadeSlideIn({
    super.key,
    required this.child,
    this.index = 0,
    this.offset = LpgTokens.spacingMd * 1.0,
  });

  final Widget child;

  /// Position among siblings, for staggering. 0 starts immediately.
  final int index;

  /// How far below its resting place the child starts, in logical pixels.
  final double offset;

  /// The stagger step and the cap on how many steps a delay may add up to.
  static final _staggerStep = LpgTokens.motionDurationMicro ~/ 2;
  static const _maxStaggerSteps = 8;

  @override
  State<LpgFadeSlideIn> createState() => _LpgFadeSlideInState();
}

class _LpgFadeSlideInState extends State<LpgFadeSlideIn>
    with SingleTickerProviderStateMixin {
  AnimationController? _controller;
  Animation<double>? _progress;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_controller != null) return;

    final duration = LpgMotion.large(context);
    if (duration == Duration.zero ||
        (MediaQuery.maybeOf(context)?.disableAnimations ?? false)) {
      return;
    }
    final steps = widget.index.clamp(0, LpgFadeSlideIn._maxStaggerSteps);
    final delay = LpgFadeSlideIn._staggerStep * steps;
    final total = delay + duration;
    final controller = AnimationController(vsync: this, duration: total);
    _controller = controller;
    _progress = CurvedAnimation(
      parent: controller,
      curve: Interval(
        delay.inMicroseconds / total.inMicroseconds,
        1,
        curve: Curves.easeOutCubic,
      ),
    );
    controller.forward();
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final progress = _progress;
    if (progress == null) return widget.child;
    return AnimatedBuilder(
      animation: progress,
      builder: (context, child) => Opacity(
        opacity: progress.value,
        child: Transform.translate(
          offset: Offset(0, (1 - progress.value) * widget.offset),
          child: child,
        ),
      ),
      child: widget.child,
    );
  }
}

/// Wraps any tappable surface with the same spring press feedback
/// [LpgButton] uses: a small scale-down on touch, an overshooting settle on
/// release. The child keeps its own ink/ripple; this only adds the physical
/// "give".
class LpgPressable extends StatefulWidget {
  const LpgPressable({
    super.key,
    required this.child,
    required this.enabled,
    this.pressedScale = 0.97,
  });

  final Widget child;
  final bool enabled;
  final double pressedScale;

  @override
  State<LpgPressable> createState() => _LpgPressableState();
}

class _LpgPressableState extends State<LpgPressable>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    value: 1.0,
    lowerBound: 0,
    upperBound: 2,
  );

  void _animateTo(double target) {
    if (MediaQuery.maybeOf(context)?.disableAnimations ?? false) {
      _controller.value = 1.0;
      return;
    }
    _controller.animateWith(
      SpringSimulation(LpgMotion.spatialSpring, _controller.value, target, 0),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled) return widget.child;
    return Listener(
      onPointerDown: (_) => _animateTo(widget.pressedScale),
      onPointerUp: (_) => _animateTo(1.0),
      onPointerCancel: (_) => _animateTo(1.0),
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) =>
            Transform.scale(scale: _controller.value, child: child),
        child: widget.child,
      ),
    );
  }
}

/// Counts a number up from zero the first time it appears, and tweens
/// between values when it changes — for balances and totals on dashboards.
class LpgCountUp extends StatelessWidget {
  const LpgCountUp({super.key, required this.value, this.style, this.format});

  final num value;
  final TextStyle? style;

  /// Formats the in-flight value; defaults to a rounded integer.
  final String Function(num value)? format;

  @override
  Widget build(BuildContext context) {
    final formatter = format ?? (num v) => v.round().toString();
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.toDouble()),
      duration: LpgMotion.large(context) * 2,
      curve: Curves.easeOutCubic,
      builder: (context, v, _) =>
          Text(formatter(v), style: style, semanticsLabel: formatter(value)),
    );
  }
}
