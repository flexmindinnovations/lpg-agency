import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// Where a step sits relative to now.
enum LpgTimelineState { done, current, upcoming, failed }

/// One step of an [LpgTimeline].
@immutable
class LpgTimelineStep {
  const LpgTimelineStep({
    required this.title,
    required this.state,
    this.subtitle,
    this.icon,
  });

  final String title;
  final String? subtitle;
  final LpgTimelineState state;

  /// Overrides the default check / dot / cross for this step.
  final IconData? icon;
}

/// A vertical progress timeline — an order's journey from placed to
/// delivered. Completed steps get a filled check and a solid connector, the
/// current step a pulsing ring, upcoming steps a hollow dot and a faint
/// connector.
class LpgTimeline extends StatelessWidget {
  const LpgTimeline({super.key, required this.steps});

  final List<LpgTimelineStep> steps;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < steps.length; i++)
          _TimelineRow(
            step: steps[i],
            isLast: i == steps.length - 1,
            nextReached:
                i < steps.length - 1 &&
                steps[i + 1].state != LpgTimelineState.upcoming,
          ),
      ],
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({
    required this.step,
    required this.isLast,
    required this.nextReached,
  });

  final LpgTimelineStep step;
  final bool isLast;
  final bool nextReached;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    const dot = LpgSpacing.lg;

    final Color color = switch (step.state) {
      LpgTimelineState.done => colors.statusSuccess,
      LpgTimelineState.current => colors.actionPrimary,
      LpgTimelineState.failed => colors.statusDanger,
      LpgTimelineState.upcoming => colors.borderStrong,
    };

    final IconData? glyph =
        step.icon ??
        switch (step.state) {
          LpgTimelineState.done => LpgIcons.check,
          LpgTimelineState.failed => LpgIcons.close,
          _ => null,
        };

    final filled =
        step.state == LpgTimelineState.done ||
        step.state == LpgTimelineState.failed;

    Widget marker = Container(
      width: dot,
      height: dot,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: filled ? color : colors.card,
        border: Border.all(color: color, width: 2),
      ),
      child: glyph == null
          ? null
          : Icon(
              glyph,
              size: LpgSizes.iconSm - 2,
              color: filled ? colors.card : color,
            ),
    );
    if (step.state == LpgTimelineState.current) {
      marker = _Pulse(color: color, child: marker);
    }

    final stateLabel = switch (step.state) {
      LpgTimelineState.done => 'completed',
      LpgTimelineState.current => 'in progress',
      LpgTimelineState.upcoming => 'not started',
      LpgTimelineState.failed => 'failed',
    };

    return Semantics(
      label:
          '${step.title}, $stateLabel'
          '${step.subtitle == null ? '' : ', ${step.subtitle}'}',
      excludeSemantics: true,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: dot,
              child: Column(
                children: [
                  marker,
                  if (!isLast)
                    Expanded(
                      child: Container(
                        width: 2,
                        margin: const EdgeInsets.symmetric(
                          vertical: LpgSpacing.xs,
                        ),
                        decoration: BoxDecoration(
                          color: nextReached
                              ? colors.statusSuccess
                              : colors.borderDefault,
                          borderRadius: BorderRadius.circular(LpgRadius.full),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: LpgSpacing.smd),
            Expanded(
              child: Padding(
                padding: EdgeInsets.only(
                  top: LpgSpacing.xs / 2,
                  bottom: isLast ? 0 : LpgSpacing.mdl,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      step.title,
                      style: text.titleSmall?.copyWith(
                        color: step.state == LpgTimelineState.upcoming
                            ? colors.textSecondary
                            : colors.textPrimary,
                      ),
                    ),
                    if (step.subtitle != null) ...[
                      const SizedBox(height: LpgSpacing.xs / 2),
                      Text(step.subtitle!, style: text.bodySmall),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A soft ring that breathes outward from the current step a few times,
/// then rests — enough to draw the eye without animating forever (which
/// would also keep `pumpAndSettle` in widget tests from ever settling).
/// Static under reduce-motion.
class _Pulse extends StatefulWidget {
  const _Pulse({required this.color, required this.child});

  final Color color;
  final Widget child;

  @override
  State<_Pulse> createState() => _PulseState();
}

class _PulseState extends State<_Pulse> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: LpgMotion.pulse,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      _controller.stop();
    } else if (!_controller.isAnimating && _controller.value == 0) {
      _controller.repeat(count: LpgMotion.pulseRepeats);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      child: widget.child,
      builder: (context, child) {
        final t = _controller.value;
        return DecoratedBox(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: widget.color.withValues(alpha: 0.35 * (1 - t)),
                spreadRadius: LpgSpacing.sm * t,
              ),
            ],
          ),
          child: child,
        );
      },
    );
  }
}
