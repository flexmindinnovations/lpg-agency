import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// The agency logo shown on the splash and sign-in screens. Replace the
/// asset to rebrand; [LpgBrandMark] handles sizing, radius and shadow.
const appLogo = AssetImage('assets/images/lpg_app_logo.jpg');

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  static const _logoSize = 112.0;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      backgroundColor: colors.canvas,
      body: Center(
        child: LpgFadeSlideIn(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const LpgBrandMark(image: appLogo, size: _logoSize),
              const SizedBox(height: LpgSpacing.xl),
              Text('LPG Agency', style: text.headlineMedium),
              const SizedBox(height: LpgSpacing.sm),
              Text(
                'Your gas, delivered safely.',
                style: text.bodyLarge?.copyWith(color: colors.textSecondary),
              ),
              const SizedBox(height: LpgSpacing.xxl),
              const LpgLoadingIndicator(),
            ],
          ),
        ),
      ),
    );
  }
}
