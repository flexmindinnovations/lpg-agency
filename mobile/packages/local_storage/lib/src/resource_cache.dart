import 'dart:convert';

import 'package:drift/drift.dart';

import 'drift/app_database.dart';

/// Cache-first read helper over the generic [CachedResources] table —
/// every screen's provider calls [read] before hitting the API, then
/// [write] to overwrite the row with the fresh response. JSON in, JSON out:
/// callers own their own `fromJson`/`toJson`, this class just persists it.
///
/// Every row belongs to [owner], the signed-in user's id, so a second person
/// signing in on the same phone never reads the first person's data. [owner]
/// is read on each call, so it follows sign-ins and sign-outs; with none
/// given, everything is kept under one anonymous owner.
final class ResourceCache {
  // The public `owner` parameter cannot be a private initializing formal.
  // ignore: prefer_initializing_formals
  const ResourceCache(this._db, {String? Function()? owner}) : _owner = owner;

  final AppDatabase _db;
  final String? Function()? _owner;

  String get _ownerId => _owner?.call() ?? '';

  Future<Map<String, dynamic>?> read(
    String resourceType,
    String resourceId,
  ) async {
    final row =
        await (_db.select(_db.cachedResources)..where(
              (t) =>
                  t.resourceType.equals(resourceType) &
                  t.resourceId.equals(resourceId) &
                  t.ownerId.equals(_ownerId),
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
            ownerId: Value(_ownerId),
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
              t.resourceId.equals(resourceId) &
              t.ownerId.equals(_ownerId),
        ))
        .go();
  }

  /// Drop every cached row, whoever owns it — called on an explicit log out.
  /// (Rows are also owner-scoped, so a forced sign-out needs no clearing for
  /// the next person to be unable to read them.)
  Future<void> clear() async {
    await _db.delete(_db.cachedResources).go();
  }

  /// All cached rows of one type, e.g. every `'order'` row for a list
  /// screen's offline fallback. Ordered most-recently-updated first.
  Future<List<Map<String, dynamic>>> readAll(String resourceType) async {
    final rows =
        await (_db.select(_db.cachedResources)
              ..where(
                (t) =>
                    t.resourceType.equals(resourceType) &
                    t.ownerId.equals(_ownerId),
              )
              ..orderBy([(t) => OrderingTerm.desc(t.updatedAt)]))
            .get();
    return rows
        .map((row) => jsonDecode(row.jsonPayload) as Map<String, dynamic>)
        .toList();
  }
}
