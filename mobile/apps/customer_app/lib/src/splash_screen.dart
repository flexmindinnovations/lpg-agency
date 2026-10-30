import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// The agency logo shown on the splash and sign-in screens. Replace the
/// asset to rebrand; [LpgBrandMark] handles sizing, radius and shadow.
const appLogo = AssetImage('assets/images/lpg_app_logo.jpg');

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const LpgSplash(
      logo: appLogo,
      title: 'LPG Agency',
      tagline: 'Your gas, delivered safely.',
    );
  }
}
