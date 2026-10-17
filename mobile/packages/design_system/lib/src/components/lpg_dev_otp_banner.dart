import 'package:flutter/material.dart';

import '../theme.dart';

/// **Testing only.** Shows a sign-in verification code on screen until an
/// SMS/WhatsApp gateway delivers it. Callers render it only when the backend's
/// dev inbox returned a code (the route does not exist in production). Remove
/// this widget and its two call sites once real delivery ships.
class LpgDevOtpBanner extends StatelessWidget {
  const LpgDevOtpBanner({required this.code, super.key});

  final String code;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Semantics(
      container: true,
      label: 'Testing only. Your verification code is $code',
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
              'Testing only: your code is',
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
