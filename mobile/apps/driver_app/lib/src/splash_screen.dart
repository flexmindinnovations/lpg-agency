import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Shown while `main()`'s startup session restore runs — the router holds
/// here on `AuthStatus.unknown`, then redirects to `/` or `/login`. Mirrors
/// the Customer App's splash so both apps feel like one product.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const LpgFadeSlideIn(
              child: LpgBrandMark(
                image: AssetImage('assets/images/lpg_app_logo.jpg'),
                size: LpgSizes.avatarLg * 1.75,
              ),
            ),
            const SizedBox(height: LpgSpacing.xl),
            Text(
              'LPG Agency',
              style: text.headlineMedium?.copyWith(color: colors.textPrimary),
            ),
            const SizedBox(height: LpgSpacing.sm),
            const LpgStatusBadge(
              label: 'DRIVER',
              severity: LpgStatusSeverity.info,
              icon: LpgIcons.truck,
            ),
            const SizedBox(height: LpgSpacing.xxl),
            const LpgLoadingIndicator(size: LpgSizes.iconLg),
          ],
        ),
      ),
    );
  }
}
