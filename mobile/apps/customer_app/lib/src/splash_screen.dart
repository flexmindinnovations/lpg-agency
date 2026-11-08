import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';

/// The agency logo shown on the splash and sign-in screens. Replace the
/// asset to rebrand; [LpgBrandMark] handles sizing, radius and shadow.
const appLogo = AssetImage('assets/images/lpg_app_logo.jpg');

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
        logo: appLogo,
        title: 'LPG Agency',
        tagline: 'Your gas, delivered safely.',
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
