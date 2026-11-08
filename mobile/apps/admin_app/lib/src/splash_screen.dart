import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';

const appLogo = AssetImage('assets/images/admin_logo.png');

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
        title: 'LPG Agency Admin',
        tagline: 'Operations & agency control',
        badge: 'Admin Console',
        badgeIcon: LpgIcons.security,
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
