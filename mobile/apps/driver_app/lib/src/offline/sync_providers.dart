import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

/// The app-wide [SyncCoordinator]. `main()` builds it (wired to the opened
/// database, the API client and the connectivity monitor) and overrides this
/// before the first frame; the default fails loudly if that's missed.
final syncCoordinatorProvider = Provider<SyncCoordinator>(
  (ref) => throw UnimplementedError(
    'syncCoordinatorProvider must be overridden in main().',
  ),
);

/// Count of operations still working through the offline queue
/// (`pending` / `error` / `syncing`) — drives the shell's sync indicator.
final pendingSyncCountProvider = StreamProvider<int>(
  (ref) => ref.watch(syncCoordinatorProvider).watchPendingCount(),
);

/// Operations that need the driver's attention — `failed` (retries exhausted
/// or a permanent 4xx) and `conflict` (the server rejected a stale
/// transition). Newest first. Surfaced by the Stage 6 sync-status screen.
final syncIssuesProvider = StreamProvider<List<SyncOperation>>(
  (ref) => ref.watch(syncCoordinatorProvider).watchIssues(),
);
