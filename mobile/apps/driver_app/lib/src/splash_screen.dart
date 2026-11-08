import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';

/// Shown while `main()`'s startup session restore runs — the router holds
/// here on `AuthStatus.unknown`, then redirects to `/` or `/login`. Shares
/// the Customer and Admin apps' splash so all three feel like one product.
class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    // While the first sign-in check cannot reach the server, say so and offer
    // Retry; the stored session is kept either way.
    return ListenableBuilder(
      listenable: auth,
      builder: (context, _) => LpgSplash(
        logo: AssetImage('assets/images/lpg_app_logo.jpg'),
        title: 'LPG Agency',
        tagline: 'Every delivery, on time.',
        badge: 'Driver',
        badgeIcon: LpgIcons.truck,
        footer: auth.restoreWaiting
            ? LpgSplashOffline(
                onRetry: auth.retryRestoreNow,
                retrying: auth.restoreRetrying,
              )
            : null,
      ),
    );
  }
}
