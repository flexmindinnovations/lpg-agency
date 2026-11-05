import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'drift_local_database.dart' show generateEncryptionKey;

/// A random 256-bit secret kept in platform secure storage (Keychain or
/// Keystore) under [name], created on first use: for data other than the
/// database that must also be encrypted at rest (proof-of-delivery photos and
/// signatures). Hex-encoded; it never touches the disk in the clear.
Future<String> loadOrCreateSecureKey(String name) async {
  const storage = FlutterSecureStorage();
  var key = await storage.read(key: name);
  if (key == null) {
    key = generateEncryptionKey();
    await storage.write(key: name, value: key);
  }
  return key;
}

/// [loadOrCreateSecureKey] as raw bytes (32 of them), for a cipher.
Future<List<int>> loadOrCreateSecureKeyBytes(String name) async =>
    hexToBytes(await loadOrCreateSecureKey(name));

/// Decodes a hex string such as `generateEncryptionKey` returns.
List<int> hexToBytes(String hex) {
  if (hex.length.isOdd) throw const FormatException('odd-length hex string');
  return [
    for (var i = 0; i < hex.length; i += 2)
      int.parse(hex.substring(i, i + 2), radix: 16),
  ];
}
