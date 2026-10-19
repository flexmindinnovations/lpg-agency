import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';

/// The app's logo tile: the brand image when one is supplied, otherwise a
/// flame glyph on the brand gradient. Splash and sign-in screens use this,
/// so swapping in the real logo is one `image:` argument at each app's
/// call site (or a new default here).
class LpgBrandMark extends StatelessWidget {
  const LpgBrandMark({super.key, this.image, this.size = LpgSizes.avatarLg});

  final ImageProvider? image;
  final double size;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final radius = BorderRadius.circular(size * 0.28);
    return Semantics(
      image: true,
      label: 'App logo',
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          borderRadius: radius,
          gradient: image == null
              ? LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: colors.heroGradient,
                )
              : null,
          color: image == null ? null : colors.card,
          boxShadow: colors.isHighContrast ? null : colors.floatingShadow,
          border: colors.isHighContrast
              ? Border.all(color: colors.borderStrong, width: 2)
              : null,
        ),
        child: ClipRRect(
          borderRadius: radius,
          child: image == null
              ? Icon(LpgIcons.flame, size: size * 0.5, color: colors.accent)
              : Image(image: image!, fit: BoxFit.cover),
        ),
      ),
    );
  }
}
