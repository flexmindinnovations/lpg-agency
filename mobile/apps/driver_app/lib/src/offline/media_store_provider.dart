import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sync_engine/sync_engine.dart';

/// On-device store for proof-of-delivery media captured before it can be
/// uploaded. `main()` builds a [FileMediaStore] under the app-support
/// directory and overrides this before the first frame.
final mediaStoreProvider = Provider<MediaStore>(
  (ref) => throw UnimplementedError(
    'mediaStoreProvider must be overridden in main().',
  ),
);
