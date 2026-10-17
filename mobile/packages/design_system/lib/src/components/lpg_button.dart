import 'package:flutter/material.dart';
import 'package:flutter/physics.dart' show SpringSimulation;

import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// Visual weight of an [LpgButton].
///
/// - [primary]: the one action a screen wants taken. Filled.
/// - [secondary]: any other action that still needs a button shape. Outlined.
/// - [text]: the lowest-emphasis inline action.
/// - [tonal]: a soft-filled middle ground, for a second action next to a
///   primary one (e.g. "Call customer" beside "Record delivery").
/// - [destructive]: cancels, deletes or fails something. Filled in the
///   danger colour so it never reads as the safe default.
enum LpgButtonVariant { primary, secondary, text, tonal, destructive }

/// The app's button. Colour carries the hierarchy, and press feedback is a
/// real spring-physics scale-down ([LpgMotion.spatialSpring]) rather than a
/// shadow change. `text` and high contrast fall back to the native Material
/// buttons, which `LpgTheme` already themes.
class LpgButton extends StatefulWidget {
  const LpgButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = LpgButtonVariant.primary,
    this.icon,
    this.trailingIcon,
    this.isLoading = false,
    this.expand = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final LpgButtonVariant variant;
  final IconData? icon;

  /// An icon after the label, e.g. a chevron on a "Continue" button.
  final IconData? trailingIcon;
  final bool isLoading;

  /// Stretches to the parent's full width.
  final bool expand;

  @override
  State<LpgButton> createState() => _LpgButtonState();
}

class _LpgButtonState extends State<LpgButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  static const _pressedScale = 0.96;

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
    final colors = context.lpgColors;
    // Loading isn't the same as disabled: a genuinely disabled button fades
    // to signal "not available", but a loading one is actively doing what
    // it was asked to do. Keep full colour and swap the label for a
    // spinner; only actual unavailability (no onPressed) dims it.
    // `unpressable` still blocks taps in both cases.
    final unpressable = widget.onPressed == null || widget.isLoading;
    final visuallyDisabled = widget.onPressed == null && !widget.isLoading;

    if (widget.variant == LpgButtonVariant.text || colors.isHighContrast) {
      return _buildFlatButton(context, colors, unpressable);
    }

    final (Color baseColor, Color textColor) = switch (widget.variant) {
      LpgButtonVariant.primary => (colors.actionPrimary, colors.textInverse),
      LpgButtonVariant.destructive => (colors.statusDanger, colors.textInverse),
      LpgButtonVariant.tonal => (
        colors.actionPrimaryContainer,
        colors.onActionPrimaryContainer,
      ),
      _ => (colors.card, colors.textPrimary),
    };

    final content = AnimatedSwitcher(
      duration: LpgMotion.small(context),
      child: widget.isLoading
          ? SizedBox(
              key: const ValueKey('loading'),
              width: LpgSizes.iconMd,
              height: LpgSizes.iconMd,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                valueColor: AlwaysStoppedAnimation<Color>(textColor),
              ),
            )
          : _label(context, textColor),
    );

    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(LpgRadius.lg),
      side: widget.variant == LpgButtonVariant.secondary
          ? BorderSide(color: colors.borderStrong)
          : BorderSide.none,
    );

    final button = Material(
      color: visuallyDisabled ? colors.surfaceOverlay : baseColor,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: unpressable ? null : widget.onPressed,
        onTapDown: unpressable ? null : (_) => _animateTo(_pressedScale),
        onTapUp: unpressable ? null : (_) => _animateTo(1.0),
        onTapCancel: unpressable ? null : () => _animateTo(1.0),
        customBorder: shape,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: LpgSizes.buttonHeight),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: LpgSpacing.lg),
            child: Center(
              widthFactor: 1,
              child: visuallyDisabled
                  ? DefaultTextStyle.merge(
                      style: TextStyle(color: colors.textDisabled),
                      child: IconTheme.merge(
                        data: IconThemeData(color: colors.textDisabled),
                        child: _label(context, colors.textDisabled),
                      ),
                    )
                  : content,
            ),
          ),
        ),
      ),
    );

    final sized = widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;

    return Semantics(
      button: true,
      enabled: !unpressable,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) =>
            Transform.scale(scale: _controller.value, child: child),
        child: sized,
      ),
    );
  }

  Widget _label(BuildContext context, Color textColor) {
    return Row(
      key: const ValueKey('label'),
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.icon != null) ...[
          Icon(widget.icon, size: LpgSizes.iconMd, color: textColor),
          const SizedBox(width: LpgSpacing.sm),
        ],
        Flexible(
          child: Text(
            widget.label,
            overflow: TextOverflow.ellipsis,
            style: context.lpgText.labelLarge?.copyWith(color: textColor),
          ),
        ),
        if (widget.trailingIcon != null) ...[
          const SizedBox(width: LpgSpacing.sm),
          Icon(widget.trailingIcon, size: LpgSizes.iconMd, color: textColor),
        ],
      ],
    );
  }

  Widget _buildFlatButton(
    BuildContext context,
    LpgColors colors,
    bool disabled,
  ) {
    final child = widget.isLoading
        ? const SizedBox(
            width: LpgSizes.iconMd,
            height: LpgSizes.iconMd,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.icon != null) ...[
                Icon(widget.icon, size: LpgSizes.iconMd),
                const SizedBox(width: LpgSpacing.sm),
              ],
              Flexible(child: Text(widget.label)),
              if (widget.trailingIcon != null) ...[
                const SizedBox(width: LpgSpacing.sm),
                Icon(widget.trailingIcon, size: LpgSizes.iconMd),
              ],
            ],
          );

    final onPressed = disabled ? null : widget.onPressed;
    final Widget button = switch (widget.variant) {
      LpgButtonVariant.primary || LpgButtonVariant.tonal => ElevatedButton(
        onPressed: onPressed,
        child: child,
      ),
      LpgButtonVariant.destructive => ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: colors.statusDanger,
          foregroundColor: colors.onHero,
        ),
        child: child,
      ),
      LpgButtonVariant.secondary => OutlinedButton(
        onPressed: onPressed,
        child: child,
      ),
      LpgButtonVariant.text => TextButton(onPressed: onPressed, child: child),
    };

    return widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}
