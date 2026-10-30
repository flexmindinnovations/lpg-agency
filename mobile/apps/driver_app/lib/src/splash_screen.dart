import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// Shown while `main()`'s startup session restore runs — the router holds
/// here on `AuthStatus.unknown`, then redirects to `/` or `/login`. Shares
/// the Customer and Admin apps' splash so all three feel like one product.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const LpgSplash(
      logo: AssetImage('assets/images/lpg_app_logo.jpg'),
      title: 'LPG Agency',
      tagline: 'Every delivery, on time.',
      badge: 'Driver',
      badgeIcon: LpgIcons.truck,
    );
  }
}
