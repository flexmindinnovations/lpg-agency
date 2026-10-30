import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// The full-screen splash every app shows while it restores the session.
///
/// A brand gradient with a soft breathing glow, a logo that springs in with
/// two rings rippling out behind it, then the name, tagline and an optional
/// badge rising in one after another, and three dots that bob while the app
/// loads. With reduce-motion on it draws the finished frame and nothing
/// moves.
class LpgSplash extends StatefulWidget {
  const LpgSplash({
    super.key,
    required this.logo,
    required this.title,
    required this.tagline,
    this.badge,
    this.badgeIcon,
  });

  final ImageProvider logo;
  final String title;
  final String tagline;

  /// A small pill under the tagline ("Admin Console", "Driver").
  final String? badge;
  final IconData? badgeIcon;

  @override
  State<LpgSplash> createState() => _LpgSplashState();
}

class _LpgSplashState extends State<LpgSplash> with TickerProviderStateMixin {
  late final AnimationController _intro = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1500),
  );
  late final AnimationController _loop = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (MediaQuery.maybeOf(context)?.disableAnimations ?? false) {
      _intro.value = 1;
      return;
    }
    _intro.forward();
    _loop.repeat();
  }

  @override
  void dispose() {
    _intro.dispose();
    _loop.dispose();
    super.dispose();
  }

  Animation<double> _interval(double begin, double end, Curve curve) =>
      CurvedAnimation(
        parent: _intro,
        curve: Interval(begin, end, curve: curve),
      );

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final gradient = colors.heroGradient;

    final logoIn = _interval(0.0, 0.55, Curves.easeOutBack);
    final logoFade = _interval(0.0, 0.3, Curves.easeOut);
    final titleIn = _interval(0.35, 0.75, Curves.easeOutCubic);
    final taglineIn = _interval(0.5, 0.88, Curves.easeOutCubic);
    final badgeIn = _interval(0.62, 1.0, Curves.easeOutCubic);

    Widget rise(Animation<double> a, Widget child) => FadeTransition(
      opacity: a,
      child: SlideTransition(
        position: Tween(
          begin: const Offset(0, 0.4),
          end: Offset.zero,
        ).animate(a),
        child: child,
      ),
    );

    return Scaffold(
      body: AnimatedBuilder(
        animation: _loop,
        builder: (context, child) {
          final t = _loop.value;
          final breathe = 0.5 + 0.5 * math.sin(t * 2 * math.pi);
          return DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  gradient.first,
                  gradient.length > 1 ? gradient.last : gradient.first,
                ],
              ),
            ),
            child: Stack(
              fit: StackFit.expand,
              children: [
                // A warm glow behind the logo that slowly breathes.
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: RadialGradient(
                        center: const Alignment(0, -0.25),
                        radius: 0.9,
                        colors: [
                          colors.accent.withValues(
                            alpha: 0.10 + 0.10 * breathe,
                          ),
                          Colors.transparent,
                        ],
                      ),
                    ),
                  ),
                ),
                // Two soft discs drifting in opposite directions.
                Positioned(
                  top: -60 + 24 * math.sin(t * 2 * math.pi),
                  right: -70,
                  child: _Disc(size: 240, alpha: 0.07),
                ),
                Positioned(
                  bottom: -90 + 24 * math.cos(t * 2 * math.pi),
                  left: -80,
                  child: _Disc(size: 300, alpha: 0.05),
                ),
                child!,
              ],
            ),
          );
        },
        child: SafeArea(
          child: Column(
            children: [
              const Spacer(flex: 5),
              SizedBox(
                width: 220,
                height: 220,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    for (final phase in const [0.0, 0.5])
                      AnimatedBuilder(
                        animation: _loop,
                        builder: (context, _) {
                          final p = (_loop.value + phase) % 1.0;
                          return Opacity(
                            opacity: (1 - p) * 0.35 * _intro.value,
                            child: Container(
                              width: 120 + 100 * p,
                              height: 120 + 100 * p,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: colors.onHero,
                                  width: 1.5,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    FadeTransition(
                      opacity: logoFade,
                      child: ScaleTransition(
                        scale: Tween(begin: 0.55, end: 1.0).animate(logoIn),
                        child: Container(
                          width: 112,
                          height: 112,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(32),
                            border: Border.all(
                              color: colors.onHero.withValues(alpha: 0.55),
                              width: 2,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.35),
                                blurRadius: 32,
                                offset: const Offset(0, 14),
                              ),
                            ],
                          ),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(30),
                            child: Image(image: widget.logo, fit: BoxFit.cover),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: LpgSpacing.lg),
              rise(
                titleIn,
                Text(
                  widget.title,
                  textAlign: TextAlign.center,
                  style: text.headlineMedium?.copyWith(
                    color: colors.onHero,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.3,
                  ),
                ),
              ),
              const SizedBox(height: LpgSpacing.sm),
              rise(
                taglineIn,
                Text(
                  widget.tagline,
                  textAlign: TextAlign.center,
                  style: text.bodyLarge?.copyWith(
                    color: colors.onHero.withValues(alpha: 0.82),
                  ),
                ),
              ),
              if (widget.badge != null) ...[
                const SizedBox(height: LpgSpacing.md),
                rise(
                  badgeIn,
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: LpgSpacing.md,
                      vertical: LpgSpacing.xs + 2,
                    ),
                    decoration: BoxDecoration(
                      color: colors.onHero.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(LpgRadius.full),
                      border: Border.all(
                        color: colors.onHero.withValues(alpha: 0.28),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (widget.badgeIcon != null) ...[
                          Icon(
                            widget.badgeIcon,
                            size: 16,
                            color: colors.onHero,
                          ),
                          const SizedBox(width: LpgSpacing.xs + 2),
                        ],
                        Text(
                          widget.badge!,
                          style: text.labelLarge?.copyWith(
                            color: colors.onHero,
                            letterSpacing: 0.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              const Spacer(flex: 4),
              _BobbingDots(controller: _loop, color: colors.onHero),
              const SizedBox(height: LpgSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}

class _Disc extends StatelessWidget {
  const _Disc({required this.size, required this.alpha});

  final double size;
  final double alpha;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      color: Colors.white.withValues(alpha: alpha),
    ),
  );
}

/// Three dots that rise and fall in sequence: "working on it".
class _BobbingDots extends StatelessWidget {
  const _BobbingDots({required this.controller, required this.color});

  final Animation<double> controller;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Loading',
      child: AnimatedBuilder(
        animation: controller,
        builder: (context, _) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < 3; i++)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Transform.translate(
                  offset: Offset(
                    0,
                    -6 *
                        math.max(
                          0,
                          math.sin((controller.value * 2 - i * 0.22) * math.pi),
                        ),
                  ),
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: color.withValues(alpha: 0.85),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
