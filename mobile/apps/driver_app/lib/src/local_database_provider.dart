import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';

/// The Driver App's on-device database (ADR-008: full offline-first, unlike
/// the Customer App's simple cache-and-refresh).
///
/// `main()` awaits [DriftLocalDatabase.open] before the first frame and
/// overrides this provider with the opened instance, so no widget ever reads
/// from a database that isn't ready yet. The default here exists only to
/// fail loudly if that override is ever missed.
final localDatabaseProvider = Provider<LocalDatabase>(
  (ref) => throw UnimplementedError(
    'localDatabaseProvider must be overridden in main() with an opened '
    'DriftLocalDatabase.',
  ),
);
