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

  /// Deletes every cached row, **whoever owns it**, that has not been written
  /// for [olderThan] (14 days by default). Returns how many were removed.
  ///
  /// The cache only holds copies of what the server has, refilled by the next
  /// successful request, and a row is rewritten on every successful refresh,
  /// so only data nobody has fetched for two weeks goes: a route from a driver
  /// who no longer uses this phone, an order nobody opened. It is also stale
  /// by then, so reading it offline would mislead more than help.
  Future<int> pruneStale({Duration olderThan = const Duration(days: 14)}) {
    final cutoff = DateTime.now().subtract(olderThan);
    return (_db.delete(
      _db.cachedResources,
    )..where((t) => t.updatedAt.isSmallerThanValue(cutoff))).go();
  }

  /// Deletes the rows of **everyone but the signed-in user** that have not been
  /// written for [olderThan] (2 days by default): the cache of a driver who has
  /// signed out of this phone, and whose data nobody here should be holding on
  /// to. Returns how many were removed.
  ///
  /// It does nothing when nobody is signed in (the cache's owner is unknown),
  /// so it can never mistake a driver whose session is still being restored for
  /// a stranger and delete their offline data. The grace period lets a driver
  /// who signs back in after a shift change still find their route cached;
  /// anything not refreshed since is refilled by their next online fetch. Rows
  /// of the signed-in user are never touched here, however old.
  Future<int> pruneOtherOwners({
    Duration olderThan = const Duration(days: 2),
  }) async {
    final owner = _owner?.call();
    if (owner == null || owner.isEmpty) return 0;
    final cutoff = DateTime.now().subtract(olderThan);
    return (_db.delete(_db.cachedResources)..where(
          (t) =>
              t.ownerId.equals(owner).not() &
              t.updatedAt.isSmallerThanValue(cutoff),
        ))
        .go();
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
