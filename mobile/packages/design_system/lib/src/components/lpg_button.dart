import 'package:flutter/material.dart';
import 'package:flutter/physics.dart' show SpringSimulation;

import '../glass.dart';
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

/// How tall an [LpgButton] is. [large] is for the one action a hurried,
/// one-handed screen is built around (the Driver's "Open this stop").
enum LpgButtonSize { regular, large }

/// Makes every [LpgButton] below it fill the width it is given, as if each had
/// `expand: true`. Used by `LpgActionRow.equal`, which hands each button an
/// equal share of a row (or the full width when it stacks).
class LpgButtonExpansion extends InheritedWidget {
  const LpgButtonExpansion({super.key, required super.child});

  static bool of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<LpgButtonExpansion>() != null;

  @override
  bool updateShouldNotify(LpgButtonExpansion old) => false;
}

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
    this.size = LpgButtonSize.regular,
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
  final LpgButtonSize size;

  @override
  State<LpgButton> createState() => _LpgButtonState();
}

class _LpgButtonState extends State<LpgButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  bool _focused = false;

  static const _pressedScale = 0.96;
  static const _focusGap = 3.0;

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

  bool _expands(BuildContext context) =>
      widget.expand || LpgButtonExpansion.of(context);

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
      _ => (colors.cardGlass, colors.textPrimary),
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
      // The paper grain is over the fill and under the label.
      child: LpgGrainLayer(
        strength: widget.variant == LpgButtonVariant.secondary
            ? LpgGlassLook.of(colors).surfaceGrain
            : LpgGlassLook.solidGrain,
        child: InkWell(
          onTap: unpressable ? null : widget.onPressed,
          onTapDown: unpressable ? null : (_) => _animateTo(_pressedScale),
          onTapUp: unpressable ? null : (_) => _animateTo(1.0),
          onTapCancel: unpressable ? null : () => _animateTo(1.0),
          onFocusChange: (focused) => setState(() => _focused = focused),
          customBorder: shape,
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: widget.size == LpgButtonSize.large
                  ? LpgSizes.buttonHeightLarge
                  : LpgSizes.buttonHeight,
            ),
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
      ),
    );

    final sized = _expands(context)
        ? SizedBox(width: double.infinity, child: button)
        : button;
    // Keyboard focus draws a 2 px ring in the focus colour, set a little off
    // the button, so it is visible against any surface in every theme.
    final ringed = Stack(
      clipBehavior: Clip.none,
      children: [
        sized,
        if (_focused)
          Positioned.fill(
            top: -_focusGap,
            left: -_focusGap,
            right: -_focusGap,
            bottom: -_focusGap,
            child: IgnorePointer(
              child: DecoratedBox(
                key: const ValueKey('focus-ring'),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(LpgRadius.lg + _focusGap),
                  border: Border.all(color: colors.borderFocus, width: 2),
                ),
              ),
            ),
          ),
      ],
    );

    return Semantics(
      button: true,
      enabled: !unpressable,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) =>
            Transform.scale(scale: _controller.value, child: child),
        child: ringed,
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

    return _expands(context)
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}
