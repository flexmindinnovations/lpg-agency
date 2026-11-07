import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// A circular avatar: the person's picture when there is one, otherwise their
/// initials on the brand gradient. Used on profile headers and anywhere a
/// person is named.
class LpgAvatar extends StatelessWidget {
  const LpgAvatar({
    super.key,
    required this.name,
    this.size = LpgSizes.avatarMd,
    this.imageUrl,
  });

  final String name;
  final double size;

  /// A link to the person's picture. While it loads, and if it cannot be
  /// loaded (expired link, no network), the initials stay showing.
  final String? imageUrl;

  /// Up to two initials from [name]: "Asha Rao" -> "AR", "asha" -> "A".
  static String initialsOf(String name) {
    final parts = name
        .trim()
        .split(RegExp(r'\s+'))
        .where((p) => p.isNotEmpty)
        .toList();
    if (parts.isEmpty) return '?';
    final first = parts.first.characters.first;
    final last = parts.length > 1 ? parts.last.characters.first : '';
    return (first + last).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final url = imageUrl;
    return Semantics(
      label: name,
      excludeSemantics: true,
      child: Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: colors.heroGradient,
          ),
          border: colors.isHighContrast
              ? Border.all(color: colors.borderStrong, width: 2)
              : null,
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            Text(
              initialsOf(name),
              style: context.lpgText.titleMedium?.copyWith(
                color: colors.onHero,
                fontSize: size * 0.38,
                fontWeight: FontWeight.w700,
              ),
            ),
            if (url != null && url.isNotEmpty)
              ClipOval(
                child: Image.network(
                  url,
                  width: size,
                  height: size,
                  fit: BoxFit.cover,
                  // Decode no larger than what is drawn.
                  cacheWidth: (size * MediaQuery.devicePixelRatioOf(context))
                      .round(),
                  gaplessPlayback: true,
                  frameBuilder: (context, child, frame, loadedSynchronously) =>
                      AnimatedOpacity(
                        opacity: frame == null && !loadedSynchronously ? 0 : 1,
                        duration: LpgMotion.small(context),
                        child: child,
                      ),
                  // Keep the initials rather than showing a broken image.
                  errorBuilder: (_, _, _) => const SizedBox.shrink(),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
