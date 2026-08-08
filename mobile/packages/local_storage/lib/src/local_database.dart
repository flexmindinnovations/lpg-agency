/// Contract for the on-device database.
///
/// Defined as an interface now so the Driver App can depend on it before Drift
/// is wired in, and so tests can substitute an in-memory implementation.
abstract interface class LocalDatabase {
  /// Open the database, applying migrations.
  Future<void> open();

  /// Close the database and release its resources.
  Future<void> close();

  /// Whether the database is currently open.
  bool get isOpen;
}

/// A no-op implementation used until Drift is wired in.
///
/// Deliberately not a stub that pretends to store things: silently accepting
/// writes and losing them would be far worse than an obvious no-op, especially
/// on a delivery-confirmation path.
final class NoopLocalDatabase implements LocalDatabase {
  bool _open = false;

  @override
  bool get isOpen => _open;

  @override
  Future<void> open() async => _open = true;

  @override
  Future<void> close() async => _open = false;
}
