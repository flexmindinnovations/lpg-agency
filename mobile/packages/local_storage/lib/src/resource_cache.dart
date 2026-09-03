import 'dart:convert';

import 'package:drift/drift.dart';

import 'drift/app_database.dart';

/// Cache-first read helper over the generic [CachedResources] table —
/// every screen's provider calls [read] before hitting the API, then
/// [write] to overwrite the row with the fresh response. JSON in, JSON out:
/// callers own their own `fromJson`/`toJson`, this class just persists it.
final class ResourceCache {
  const ResourceCache(this._db);

  final AppDatabase _db;

  Future<Map<String, dynamic>?> read(
    String resourceType,
    String resourceId,
  ) async {
    final row =
        await (_db.select(_db.cachedResources)..where(
              (t) =>
                  t.resourceType.equals(resourceType) &
                  t.resourceId.equals(resourceId),
            ))
            .getSingleOrNull();
    if (row == null) return null;
    return jsonDecode(row.jsonPayload) as Map<String, dynamic>;
  }

  Future<void> write(
    String resourceType,
    String resourceId,
    Map<String, dynamic> json,
  ) async {
    await _db
        .into(_db.cachedResources)
        .insertOnConflictUpdate(
          CachedResourcesCompanion.insert(
            resourceType: resourceType,
            resourceId: resourceId,
            jsonPayload: jsonEncode(json),
            updatedAt: Value(DateTime.now()),
          ),
        );
  }

  /// Evict one row — e.g. an active route the backend now reports as gone
  /// (`404`), so the next offline read doesn't resurrect it.
  Future<void> delete(String resourceType, String resourceId) async {
    await (_db.delete(_db.cachedResources)..where(
          (t) =>
              t.resourceType.equals(resourceType) &
              t.resourceId.equals(resourceId),
        ))
        .go();
  }

  /// Drop every cached row — called on logout so the next user on this
  /// device never sees the previous one's data.
  Future<void> clear() async {
    await _db.delete(_db.cachedResources).go();
  }

  /// All cached rows of one type, e.g. every `'order'` row for a list
  /// screen's offline fallback. Ordered most-recently-updated first.
  Future<List<Map<String, dynamic>>> readAll(String resourceType) async {
    final rows =
        await (_db.select(_db.cachedResources)
              ..where((t) => t.resourceType.equals(resourceType))
              ..orderBy([(t) => OrderingTerm.desc(t.updatedAt)]))
            .get();
    return rows
        .map((row) => jsonDecode(row.jsonPayload) as Map<String, dynamic>)
        .toList();
  }
}
