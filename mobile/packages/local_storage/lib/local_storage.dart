/// Local storage foundation for offline-capable features.
///
/// Phase 1 provides the seam only. The Drift schema, the sync queue and
/// conflict resolution are Phase 5 and Phase 11 work (D-24, ADR-008) — this
/// package exists now so the Driver App's structure is offline-ready from the
/// start rather than being restructured later.
///
/// Two decisions are already fixed by the architecture and must hold when the
/// implementation lands:
///
///   * The database is encrypted at rest (SQLCipher), because it will hold
///     KYC-adjacent and payment-adjacent data offline.
///   * Every mutation is written locally first and queued for sync; the UI is
///     optimistic.
library;

export 'src/local_database.dart';
