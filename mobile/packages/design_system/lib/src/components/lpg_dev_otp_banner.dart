import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import '../tone.dart';

/// **Testing only.** Shows a sign-in verification code on screen until an
/// SMS/WhatsApp gateway delivers it. Callers render it only when the backend's
/// dev inbox returned a code (the route does not exist in production). Remove
/// this widget and its two call sites once real delivery ships.
class LpgDevOtpBanner extends StatelessWidget {
  const LpgDevOtpBanner({required this.code, super.key});

  /// Key on the code text, so widget tests in both apps can find it.
  static const codeKey = Key('dev-otp-code');

  final String code;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final accent = LpgTone.primary.foreground(colors);

    return Semantics(
      container: true,
      label: 'Testing only. Your verification code is $code',
      child: Container(
        padding: const EdgeInsets.all(LpgSpacing.md),
        decoration: BoxDecoration(
          color: LpgTone.primary.container(colors),
          borderRadius: BorderRadius.circular(LpgRadius.lg),
          border: Border.all(color: colors.borderFocus),
        ),
        child: Column(
          children: [
            Text(
              'Testing only: your code is',
              style: text.labelMedium?.copyWith(color: colors.textSecondary),
            ),
            const SizedBox(height: LpgSpacing.xs),
            SelectableText(
              code,
              key: codeKey,
              style: text.headlineMedium?.copyWith(
                color: accent,
                letterSpacing: LpgSpacing.sm,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
