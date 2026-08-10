import 'dart:io';
import 'dart:math';

import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import 'drift/app_database.dart';
import 'local_database.dart';

const _secureStorageKeyName = 'local_storage.sqlcipher_key';

/// Generates a random 256-bit SQLCipher passphrase, hex-encoded.
String generateEncryptionKey() {
  final random = Random.secure();
  final bytes = List<int>.generate(32, (_) => random.nextInt(256));
  return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
}

Future<String> _defaultLoadEncryptionKey() async {
  const secureStorage = FlutterSecureStorage();
  var key = await secureStorage.read(key: _secureStorageKeyName);
  if (key == null) {
    key = generateEncryptionKey();
    await secureStorage.write(key: _secureStorageKeyName, value: key);
  }
  return key;
}

Future<File> _defaultResolveFile() async {
  final directory = await getApplicationSupportDirectory();
  return File(p.join(directory.path, 'lpg_local.sqlite'));
}

/// [LocalDatabase] backed by an SQLCipher-encrypted Drift/SQLite database
/// (docs/architecture/05-mobile-architecture.md §7, ADR-034).
///
/// The encryption key never leaves the device: generated once with a
/// cryptographically secure RNG, then held in platform secure storage
/// (Keychain/Keystore) via `flutter_secure_storage` — never written to disk
/// in plaintext, never sent to the server.
///
/// [loadEncryptionKey] and [resolveFile] default to platform secure storage
/// and the app's support directory respectively; tests inject fakes for both
/// so they never touch a platform channel.
final class DriftLocalDatabase implements LocalDatabase {
  DriftLocalDatabase({
    Future<String> Function()? loadEncryptionKey,
    Future<File> Function()? resolveFile,
  }) : _loadEncryptionKey = loadEncryptionKey ?? _defaultLoadEncryptionKey,
       _resolveFile = resolveFile ?? _defaultResolveFile;

  final Future<String> Function() _loadEncryptionKey;
  final Future<File> Function() _resolveFile;
  AppDatabase? _db;

  @override
  bool get isOpen => _db != null;

  /// The underlying Drift database. Only valid once [open] has completed.
  AppDatabase get database {
    final db = _db;
    if (db == null) {
      throw StateError('DriftLocalDatabase.open() must be called first.');
    }
    return db;
  }

  @override
  Future<void> open() async {
    if (_db != null) return;

    final key = await _loadEncryptionKey();
    final file = await _resolveFile();

    final executor = NativeDatabase.createInBackground(
      file,
      setup: (rawDb) => rawDb.execute("PRAGMA key = \"x'$key'\";"),
    );

    final db = AppDatabase(executor);
    try {
      // Force the connection open now, not lazily on first query — a wrong
      // or corrupt key must fail loudly here, not on some unrelated later
      // call.
      await db.customSelect('SELECT 1').getSingle();
    } catch (_) {
      // Otherwise the background isolate NativeDatabase.createInBackground
      // spawned is orphaned, holding its file handle open indefinitely.
      await db.close();
      rethrow;
    }
    _db = db;
  }

  @override
  Future<void> close() async {
    await _db?.close();
    _db = null;
  }
}
