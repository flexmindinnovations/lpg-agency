import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import '../tone.dart';

/// An icon on a rounded, tinted square — the leading visual of list rows,
/// stat tiles, quick actions and banners. One widget so the square's size,
/// radius and tint stay identical everywhere.
class LpgIconBox extends StatelessWidget {
  const LpgIconBox({
    super.key,
    required this.icon,
    this.tone = LpgTone.primary,
    this.size = LpgSizes.iconBox,
  });

  final IconData icon;
  final LpgTone tone;
  final double size;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: tone.container(colors),
        borderRadius: BorderRadius.circular(size * 0.3),
        border: colors.isHighContrast
            ? Border.all(color: tone.foreground(colors), width: 1.5)
            : null,
      ),
      alignment: Alignment.center,
      child: ExcludeSemantics(
        child: Icon(icon, size: size * 0.5, color: tone.foreground(colors)),
      ),
    );
  }
}
