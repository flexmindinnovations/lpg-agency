import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'src/router.dart';

/// Customer App entry point.
///
/// Shell only. Registration, booking, tracking, payments and complaints are
/// each built in their own phase, behind their own plan.
void main() {
  runApp(const ProviderScope(child: CustomerApp()));
}

class CustomerApp extends ConsumerWidget {
  const CustomerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'LPG Agency',
      theme: LpgTheme.light,
      darkTheme: LpgTheme.dark,
      // Following the platform setting rather than pinning a theme, matching
      // the dashboard's `system` default.
      themeMode: ThemeMode.system,
      routerConfig: ref.watch(routerProvider),
      debugShowCheckedModeBanner: false,
    );
  }
}
