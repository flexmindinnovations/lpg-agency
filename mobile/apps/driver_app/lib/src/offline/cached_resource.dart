// The private-field assignment in the constructor can't be an initializing
// formal: the named param is public (`cache`) and the field is private
// (`_cache`), and Dart 3 forbids private named parameters.
// ignore_for_file: prefer_initializing_formals

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';

import '../api_provider.dart';
import '../local_database_provider.dart';

/// The on-device read cache, or `null` when the database isn't a real
/// `DriftLocalDatabase` (widget tests wire a `NoopLocalDatabase`). A `null`
/// cache turns [CacheFirstReader] into a plain pass-through — offline caching
/// is a progressive enhancement, never a hard dependency.
final resourceCacheProvider = Provider<ResourceCache?>((ref) {
  final db = ref.watch(localDatabaseProvider);
  return db is DriftLocalDatabase ? ResourceCache(db.database) : null;
});

/// Cache-first single-resource reads for the driver's route/stop/order data,
/// so the app keeps working through a signal dead zone (ADR-008).
final cachedResourceProvider = Provider<CacheFirstReader>(
  (ref) => CacheFirstReader(
    cache: ref.watch(resourceCacheProvider),
    dio: ref.watch(apiClientProvider).dio,
  ),
);

/// Wraps a `GET` returning a JSON object: on success it writes the fresh
/// body through to [ResourceCache] and returns it; on a network failure it
/// returns the last cached body, or rethrows if there's nothing cached.
///
/// Hits `dio` directly rather than an `api_client` wrapper (which parses and
/// discards the raw JSON) — the raw body is what gets cached and re-parsed
/// on the way back out, so the cached copy is byte-faithful to the server's.
class CacheFirstReader {
  CacheFirstReader({required ResourceCache? cache, required Dio dio})
    : _cache = cache,
      _dio = dio;

  final ResourceCache? _cache;
  final Dio _dio;

  Future<Map<String, dynamic>?> getMap(
    String path, {
    required String type,
    required String id,
    Map<String, dynamic>? queryParameters,
    bool Function(DioException e) absentWhen = _never,
  }) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: queryParameters,
      );
      final data = res.data;
      if (data != null) {
        await _cache?.write(type, id, data);
        return data;
      }
      return _cache?.read(type, id);
    } on DioException catch (e) {
      if (absentWhen(e)) {
        // The resource genuinely no longer exists — evict, don't resurrect.
        await _cache?.delete(type, id);
        return null;
      }
      final cached = await _cache?.read(type, id);
      if (cached != null) return cached;
      rethrow;
    }
  }

  static bool _never(DioException _) => false;
}
