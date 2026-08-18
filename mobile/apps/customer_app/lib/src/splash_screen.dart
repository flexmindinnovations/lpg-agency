import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: colors.surfaceBase,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: colors.actionPrimary.withValues(alpha: 0.2),
                    blurRadius: 24,
                    offset: const Offset(0, 8),
                  ),
                ],
                image: const DecorationImage(
                  image: AssetImage('assets/images/lpg_app_logo.jpg'),
                  fit: BoxFit.cover,
                ),
              ),
            ),
            const SizedBox(height: 32),
            Text(
              'LPG Agency',
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w800,
                color: colors.textPrimary,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Management Platform',
              style: theme.textTheme.bodyLarge?.copyWith(
                color: colors.textSecondary,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 64),
            SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(colors.actionPrimary),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
