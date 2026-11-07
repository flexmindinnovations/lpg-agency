import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Small per-device settings (the chosen theme, say) kept in platform secure
/// storage, the one store every app already uses. Nothing here is secret; it
/// is simply the durable key-value store that needs no extra dependency.
class SecureValueStore {
  const SecureValueStore();

  Future<String?> read(String key) =>
      const FlutterSecureStorage().read(key: key);

  Future<void> write(String key, String value) =>
      const FlutterSecureStorage().write(key: key, value: value);
}
