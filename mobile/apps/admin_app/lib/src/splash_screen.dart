import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

const appLogo = AssetImage('assets/images/admin_logo.png');

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const LpgSplash(
      logo: appLogo,
      title: 'LPG Agency Admin',
      tagline: 'Operations & agency control',
      badge: 'Admin Console',
      badgeIcon: LpgIcons.security,
    );
  }
}
