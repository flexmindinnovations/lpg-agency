import 'package:flutter/material.dart';

import '../theme.dart';

/// Shows a sign-in verification code on screen until an SMS provider exists.
/// Callers render it only when the backend returned a `dev_otp` (never in
/// production), so it disappears without any code change once real delivery
/// ships.
class LpgDevOtpBanner extends StatelessWidget {
  const LpgDevOtpBanner({required this.code, super.key});

  final String code;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Semantics(
      container: true,
      label: 'Your verification code is $code',
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: colors.actionPrimary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: colors.actionPrimary.withValues(alpha: 0.3),
          ),
        ),
        child: Column(
          children: [
            Text(
              'Your verification code',
              style: theme.textTheme.labelMedium?.copyWith(
                color: colors.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              code,
              style: theme.textTheme.headlineMedium?.copyWith(
                color: colors.actionPrimary,
                fontWeight: FontWeight.w800,
                letterSpacing: 6,
              ),
            ),
          ],
        ),
      ),
    );
  }
}