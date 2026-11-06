import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../glass.dart';
import '../haptics.dart';
import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// One tab of an [LpgNavigationBar].
@immutable
class LpgNavDestination {
  const LpgNavDestination({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    this.badgeCount = 0,
  });

  final IconData icon;

  /// The filled variant, so the active tab is marked by weight as well as
  /// colour.
  final IconData selectedIcon;
  final String label;

  /// Shows a count badge on the icon when above zero.
  final int badgeCount;
}

/// The bottom navigation bar both apps' shells use.
///
/// Every tab shows just its icon; the active one grows into a pill that also
/// carries its label. Switching tab is one continuous motion: the old pill
/// shrinks back to an icon while the new one widens, the label wipes in
/// beside its icon, and the icon pops as it fills. Under the platform's
/// reduce-motion setting the change is instant.
///
/// The active tab is marked by shape, a filled icon and a visible label, not
/// by colour alone. On a see-through card surface, lifted off content by a
/// hairline (a 2 px border and fully opaque in high contrast).
class LpgNavigationBar extends StatefulWidget {
  const LpgNavigationBar({
    super.key,
    required this.destinations,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  final List<LpgNavDestination> destinations;
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  /// Height of the pill, which is also the smallest tap target.
  static const double pillHeight = LpgSizes.touchTarget;

  @override
  State<LpgNavigationBar> createState() => _LpgNavigationBarState();
}

class _LpgNavigationBarState extends State<LpgNavigationBar>
    with SingleTickerProviderStateMixin {
  static const _curve = Curves.easeInOutCubicEmphasized;

  /// Space either side of the icon and label inside the active pill.
  static const _pillPadding = LpgSpacing.md;
  static const _iconGap = LpgSpacing.sm;

  late final AnimationController _controller = AnimationController(
    vsync: this,
    value: 1,
  );
  late double _from = widget.selectedIndex.toDouble();
  late double _to = widget.selectedIndex.toDouble();

  /// Where the active pill is, as a position between two tabs: 1.0 is
  /// exactly on the second tab.
  double get _position => _from + (_to - _from) * _curve.transform(_t);

  double get _t => _controller.value;

  @override
  void didUpdateWidget(LpgNavigationBar old) {
    super.didUpdateWidget(old);
    if (old.selectedIndex == widget.selectedIndex) return;
    final instant = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final duration = LpgMotion.large(context);
    _from = _position;
    _to = widget.selectedIndex.toDouble();
    if (instant || duration == Duration.zero) {
      _from = _to;
      _controller.value = 1;
      return;
    }
    _controller.duration = duration;
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final labelStyle = (context.lpgText.labelLarge ?? const TextStyle())
        .copyWith(fontWeight: FontWeight.w700);

    final bar = DecoratedBox(
      decoration: BoxDecoration(
        // See-through, like a card: the page shows softly through the bar.
        color: colors.barGlass,
        border: Border(
          top: BorderSide(
            color: colors.isHighContrast
                ? colors.borderStrong
                : colors.borderDefault,
            width: colors.isHighContrast ? 2 : 1,
          ),
        ),
      ),
      // The bar's height is fixed, so cap the system font scale inside it
      // (the tooltip still carries the full name for screen readers).
      child: MediaQuery.withClampedTextScaling(
        maxScaleFactor: 1.1,
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: LpgSpacing.smd,
              vertical: LpgSpacing.smd,
            ),
            child: SizedBox(
              height: LpgNavigationBar.pillHeight,
              child: LayoutBuilder(
                builder: (context, box) => AnimatedBuilder(
                  animation: _controller,
                  builder: (context, _) =>
                      _items(context, box.maxWidth, labelStyle),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    // Grain on the bar like on a card; no blur, since the page does not scroll
    // under the bar and there is nothing sharp behind it to blur.
    return colors.isHighContrast
        ? bar
        : LpgGlassPane(radius: BorderRadius.zero, child: bar);
  }

  Widget _items(BuildContext context, double width, TextStyle labelStyle) {
    final colors = context.lpgColors;
    final scaler = MediaQuery.textScalerOf(context);
    final destinations = widget.destinations;
    final count = destinations.length;
    final hc = colors.isHighContrast;

    // The active pill is as wide as its own label needs, but never so wide
    // that the other tabs fall below a tap target.
    const chrome = _pillPadding * 2 + LpgSizes.iconLg + _iconGap;
    final maxActive = count == 1
        ? width
        : width - (count - 1) * LpgNavigationBar.pillHeight;
    final actives = [
      for (final d in destinations)
        math.min(_labelWidth(d.label, labelStyle, scaler) + chrome, maxActive),
    ];
    final position = _position.clamp(0.0, count - 1.0);
    final lower = position.floor();
    final upper = position.ceil();
    final between = position - lower;
    // While the pill travels, its width eases from one label's to the next.
    final travelling =
        actives[lower] + (actives[upper] - actives[lower]) * between;
    final rest = count == 1 ? width : (width - travelling) / (count - 1);

    final children = <Widget>[];
    var left = 0.0;
    for (var i = 0; i < count; i++) {
      // 1 when this tab is the active one, 0 when not, between while the
      // pill travels past it.
      final weight = (1 - (i - position).abs()).clamp(0.0, 1.0);
      final itemWidth = rest + (actives[i] - rest) * weight;
      children.add(
        Positioned(
          left: left,
          width: itemWidth,
          top: 0,
          bottom: 0,
          child: _Item(
            destination: destinations[i],
            weight: weight,
            selected: i == widget.selectedIndex,
            labelWidth: math.max(0.0, actives[i] - chrome),
            labelStyle: labelStyle,
            highContrast: hc,
            onTap: () {
              if (i != widget.selectedIndex) LpgHaptics.selection();
              widget.onDestinationSelected(i);
            },
          ),
        ),
      );
      left += itemWidth;
    }
    return Stack(children: children);
  }

  static double _labelWidth(String label, TextStyle style, TextScaler scaler) {
    final painter = TextPainter(
      text: TextSpan(text: label, style: style),
      textDirection: TextDirection.ltr,
      textScaler: scaler,
      maxLines: 1,
    )..layout();
    final width = painter.width;
    painter.dispose();
    return width.ceilToDouble();
  }
}

class _Item extends StatelessWidget {
  const _Item({
    required this.destination,
    required this.weight,
    required this.selected,
    required this.labelWidth,
    required this.labelStyle,
    required this.highContrast,
    required this.onTap,
  });

  final LpgNavDestination destination;
  final double weight;
  final bool selected;
  final double labelWidth;
  final TextStyle labelStyle;
  final bool highContrast;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final idle = colors.textSecondary;
    final active = highContrast
        ? colors.textInverse
        : colors.onActionPrimaryContainer;
    final pill = highContrast
        ? colors.actionPrimary
        : colors.actionPrimaryContainer;

    final icon = weight > 0.5 ? destination.selectedIcon : destination.icon;
    // A small pop as the icon fills, back to 1 at both ends of the motion.
    final pop = 1 + 0.22 * math.sin(math.pi * weight);
    final ink = Color.lerp(idle, active, weight)!;
    final count = destination.badgeCount;

    Widget glyph = Icon(icon, size: LpgSizes.iconLg, color: ink);
    if (count > 0) {
      glyph = Badge(label: Text(count > 99 ? '99+' : '$count'), child: glyph);
    }

    final name = count > 0
        ? '${destination.label}, $count new'
        : destination.label;

    return Semantics(
      button: true,
      selected: selected,
      label: name,
      onTap: onTap,
      excludeSemantics: true,
      child: Tooltip(
        message: name,
        excludeFromSemantics: true,
        child: InkResponse(
          onTap: onTap,
          containedInkWell: true,
          highlightShape: BoxShape.rectangle,
          customBorder: const StadiumBorder(),
          child: Stack(
            alignment: Alignment.center,
            children: [
              if (weight > 0)
                Positioned.fill(
                  child: Align(
                    child: FractionallySizedBox(
                      widthFactor: weight,
                      heightFactor: 1,
                      child: DecoratedBox(
                        decoration: ShapeDecoration(
                          color: pill,
                          shape: const StadiumBorder(),
                        ),
                      ),
                    ),
                  ),
                ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Transform.scale(scale: pop, child: glyph),
                  // The label is always laid out (so it is the right width),
                  // and wiped in from its icon as the pill widens.
                  ClipRect(
                    child: Align(
                      alignment: Alignment.centerLeft,
                      widthFactor: weight,
                      child: Padding(
                        padding: const EdgeInsets.only(
                          left: _LpgNavigationBarState._iconGap,
                        ),
                        child: SizedBox(
                          width: labelWidth,
                          child: Text(
                            destination.label,
                            style: labelStyle.copyWith(color: active),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            softWrap: false,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
