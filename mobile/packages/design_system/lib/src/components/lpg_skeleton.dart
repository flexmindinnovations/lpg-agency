import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// Sweeps a soft highlight across its [child]'s placeholder shapes — the
/// loading state for content whose layout is known in advance (lists,
/// cards), so the screen holds its shape instead of collapsing to a
/// spinner.
///
/// The sweep stops under reduce-motion (the placeholders stay, static).
class LpgShimmer extends StatefulWidget {
  const LpgShimmer({super.key, required this.child});

  final Widget child;

  @override
  State<LpgShimmer> createState() => _LpgShimmerState();
}

class _LpgShimmerState extends State<LpgShimmer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: LpgMotion.shimmer,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final base = colors.surfaceOverlay;
    final highlight = colors.card;

    return Semantics(
      label: 'Loading',
      liveRegion: true,
      child: ExcludeSemantics(
        child: AnimatedBuilder(
          animation: _controller,
          child: widget.child,
          builder: (context, child) => ShaderMask(
            blendMode: BlendMode.srcATop,
            shaderCallback: (bounds) {
              final dx = (_controller.value * 3 - 1) * bounds.width;
              return LinearGradient(
                colors: [base, highlight, base],
                stops: const [0.35, 0.5, 0.65],
                transform: _SlideGradient(dx),
              ).createShader(bounds);
            },
            child: child,
          ),
        ),
      ),
    );
  }
}

class _SlideGradient extends GradientTransform {
  const _SlideGradient(this.dx);

  final double dx;

  @override
  Matrix4 transform(Rect bounds, {TextDirection? textDirection}) =>
      Matrix4.translationValues(dx, 0, 0);
}

/// One placeholder block. Put several inside an [LpgShimmer].
class LpgSkeleton extends StatelessWidget {
  const LpgSkeleton({
    super.key,
    this.width,
    this.height = LpgSpacing.md,
    this.radius = LpgRadius.sm,
  });

  /// A circular placeholder, for avatars and icon boxes.
  const LpgSkeleton.circle({super.key, required double size})
    : width = size,
      height = size,
      radius = LpgRadius.full;

  final double? width;
  final double height;
  final double radius;

  @override
  Widget build(BuildContext context) => Container(
    width: width,
    height: height,
    decoration: BoxDecoration(
      color: context.lpgColors.surfaceOverlay,
      borderRadius: BorderRadius.circular(radius),
    ),
  );
}

/// A shimmering stand-in for a list of cards — the default loading state
/// of every list screen.
class LpgSkeletonList extends StatelessWidget {
  const LpgSkeletonList({
    super.key,
    this.itemCount = 5,
    this.padding = LpgSpacing.page,
  });

  final int itemCount;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return LpgShimmer(
      child: ListView.separated(
        padding: padding,
        // Shrink-wrapped and non-scrolling, so it can stand in for a list
        // both as a whole screen body and inside another scroll view.
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: itemCount,
        separatorBuilder: (_, _) => const SizedBox(height: LpgSpacing.smd),
        itemBuilder: (_, _) => Container(
          padding: const EdgeInsets.all(LpgSpacing.md),
          decoration: BoxDecoration(
            color: colors.card,
            borderRadius: LpgRadius.cardRadius,
            border: Border.all(color: colors.borderDefault),
          ),
          child: const Row(
            children: [
              LpgSkeleton(
                width: LpgSizes.iconBox,
                height: LpgSizes.iconBox,
                radius: LpgRadius.lg,
              ),
              SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LpgSkeleton(width: 140, height: LpgSpacing.smd + 2),
                    SizedBox(height: LpgSpacing.sm),
                    LpgSkeleton(width: 90, height: LpgSpacing.smd - 2),
                  ],
                ),
              ),
              LpgSkeleton(
                width: 64,
                height: LpgSpacing.mdl,
                radius: LpgRadius.full,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
