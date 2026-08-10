import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _accessTokenKey = 'auth.access_token';
const _refreshTokenKey = 'auth.refresh_token';

Future<void> _defaultWrite(String key, String value) async {
  const storage = FlutterSecureStorage();
  await storage.write(key: key, value: value);
}

Future<String?> _defaultRead(String key) async {
  const storage = FlutterSecureStorage();
  return storage.read(key: key);
}

Future<void> _defaultDelete(String key) async {
  const storage = FlutterSecureStorage();
  await storage.delete(key: key);
}

/// Durable storage for the refresh token across app restarts.
///
/// Unlike the Dashboard's `HttpOnly` cookie (browser-managed, invisible to
/// script), a mobile app has no equivalent — the refresh token has to be
/// persisted somewhere the app itself controls. Platform secure storage
/// (Keychain/Keystore) is the mobile-idiomatic equivalent: encrypted at
/// rest, scoped to this app, same trust boundary `local_storage`'s
/// `DriftLocalDatabase` already relies on for its SQLCipher key.
abstract interface class TokenStorage {
  Future<void> saveTokens({required String accessToken, String? refreshToken});
  Future<String?> readAccessToken();
  Future<String?> readRefreshToken();
  Future<void> clear();
}

/// [TokenStorage] backed by `flutter_secure_storage`.
///
/// [write]/[read]/[delete] default to real platform secure storage calls;
/// tests inject in-memory fakes for all three so they never touch a
/// platform channel — the exact constructor-injectable-functions pattern
/// `local_storage`'s `DriftLocalDatabase` established.
final class SecureTokenStorage implements TokenStorage {
  SecureTokenStorage({
    Future<void> Function(String key, String value)? write,
    Future<String?> Function(String key)? read,
    Future<void> Function(String key)? delete,
  }) : _write = write ?? _defaultWrite,
       _read = read ?? _defaultRead,
       _delete = delete ?? _defaultDelete;

  final Future<void> Function(String key, String value) _write;
  final Future<String?> Function(String key) _read;
  final Future<void> Function(String key) _delete;

  @override
  Future<void> saveTokens({
    required String accessToken,
    String? refreshToken,
  }) async {
    await _write(_accessTokenKey, accessToken);
    if (refreshToken != null) {
      await _write(_refreshTokenKey, refreshToken);
    }
  }

  @override
  Future<String?> readAccessToken() => _read(_accessTokenKey);

  @override
  Future<String?> readRefreshToken() => _read(_refreshTokenKey);

  @override
  Future<void> clear() async {
    await _delete(_accessTokenKey);
    await _delete(_refreshTokenKey);
  }
}
