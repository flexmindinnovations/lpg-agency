import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// A circular avatar showing a person's initials on the brand gradient.
/// Used on profile headers and anywhere a person is named.
class LpgAvatar extends StatelessWidget {
  const LpgAvatar({
    super.key,
    required this.name,
    this.size = LpgSizes.avatarMd,
  });

  final String name;
  final double size;

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
        child: Text(
          initialsOf(name),
          style: context.lpgText.titleMedium?.copyWith(
            color: colors.onHero,
            fontSize: size * 0.38,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}
