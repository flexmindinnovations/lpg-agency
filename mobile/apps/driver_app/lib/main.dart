import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';

import 'src/local_database_provider.dart';
import 'src/router.dart';

/// Driver App entry point.
///
/// Shell only. Assigned deliveries, route, vehicle inventory, OTP verification, proof of
/// delivery and payment collection each arrive in their own phase.
///
/// The on-device database is opened here, before the first frame, so the
/// rest of the app can assume it is always ready (ADR-008 offline-first).
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final localDatabase = DriftLocalDatabase();
  await localDatabase.open();

  runApp(
    ProviderScope(
      overrides: [localDatabaseProvider.overrideWithValue(localDatabase)],
      child: const DriverApp(),
    ),
  );
}

class DriverApp extends ConsumerWidget {
  const DriverApp({super.key});

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
