import 'package:flutter/material.dart';
import 'package:flutter/physics.dart' show SpringSimulation;

import '../motion.dart';
import '../theme.dart';
import '../tokens.dart';

/// Visual weight of an [LpgButton] — primary for the one action a screen
/// wants taken, secondary for anything else that still needs a button
/// shape, text for the lowest-emphasis inline action.
enum LpgButtonVariant { primary, secondary, text }

/// A flat, tonal Material 3 Expressive button. Colour and shape carry the
/// hierarchy — filled stadium for primary, outlined stadium for secondary —
/// and press feedback is a real spring-physics scale-down
/// ([LpgMotion.spatialSpring]) rather than a shadow or gradient change,
/// matching M3 Expressive's "alive" motion model. `text` variant and high
/// contrast both fall back to native Flutter `TextButton`/`ElevatedButton`/
/// `OutlinedButton` — already correctly M3-themed via `LpgTheme`'s
/// `elevatedButtonTheme`, nothing custom needed there.
class LpgButton extends StatefulWidget {
  const LpgButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = LpgButtonVariant.primary,
    this.icon,
    this.isLoading = false,
    this.expand = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final LpgButtonVariant variant;
  final IconData? icon;
  final bool isLoading;

  /// Stretches to the parent's full width.
  final bool expand;

  @override
  State<LpgButton> createState() => _LpgButtonState();
}

class _LpgButtonState extends State<LpgButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  static const _pressedScale = 0.95;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, value: 1.0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _animateTo(double target) {
    _controller.animateWith(
      SpringSimulation(LpgMotion.spatialSpring, _controller.value, target, 0),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final disabled = widget.onPressed == null || widget.isLoading;

    if (widget.variant == LpgButtonVariant.text || colors.isHighContrast) {
      return _buildFlatButton(context, colors, theme, disabled);
    }

    final baseColor = widget.variant == LpgButtonVariant.primary
        ? colors.actionPrimary
        : colors.surfaceRaised;

    final textColor = widget.variant == LpgButtonVariant.primary
        ? colors.textInverse
        : colors.textPrimary;

    Widget content = widget.isLoading
        ? SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(textColor),
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.icon != null) ...[
                Icon(widget.icon, size: 18, color: textColor),
                const SizedBox(width: LpgTokens.spacingSm * 1.0),
              ],
              Text(
                widget.label,
                style: theme.textTheme.labelLarge?.copyWith(
                  color: textColor,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          );

    final shape = StadiumBorder(
      side: widget.variant == LpgButtonVariant.secondary
          ? BorderSide(color: colors.borderDefault)
          : BorderSide.none,
    );

    final button = Material(
      color: disabled ? baseColor.withValues(alpha: 0.5) : baseColor,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: disabled ? null : widget.onPressed,
        onTapDown: disabled ? null : (_) => _animateTo(_pressedScale),
        onTapUp: disabled ? null : (_) => _animateTo(1.0),
        onTapCancel: disabled ? null : () => _animateTo(1.0),
        customBorder: shape,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: LpgTokens.spacingLg * 1.0,
            vertical: LpgTokens.spacingMd * 1.0,
          ),
          child: content,
        ),
      ),
    );

    final sized = widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) =>
          Transform.scale(scale: _controller.value, child: child),
      child: sized,
    );
  }

  Widget _buildFlatButton(
    BuildContext context,
    LpgColors colors,
    ThemeData theme,
    bool disabled,
  ) {
    final child = widget.isLoading
        ? const SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.icon != null) ...[
                Icon(widget.icon, size: 18),
                const SizedBox(width: LpgTokens.spacingSm * 1.0),
              ],
              Text(widget.label),
            ],
          );

    final Widget button = switch (widget.variant) {
      LpgButtonVariant.primary => ElevatedButton(
        onPressed: disabled ? null : widget.onPressed,
        child: child,
      ),
      LpgButtonVariant.secondary => OutlinedButton(
        onPressed: disabled ? null : widget.onPressed,
        child: child,
      ),
      LpgButtonVariant.text => TextButton(
        onPressed: disabled ? null : widget.onPressed,
        child: child,
      ),
    };

    return widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}
