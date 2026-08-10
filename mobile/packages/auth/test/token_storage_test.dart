import 'package:auth/auth.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SecureTokenStorage', () {
    late Map<String, String> backingStore;
    late SecureTokenStorage storage;

    setUp(() {
      backingStore = {};
      storage = SecureTokenStorage(
        write: (key, value) async => backingStore[key] = value,
        read: (key) async => backingStore[key],
        delete: (key) async => backingStore.remove(key),
      );
    });

    test('round-trips both tokens', () async {
      await storage.saveTokens(
        accessToken: 'access-1',
        refreshToken: 'refresh-1',
      );

      expect(await storage.readAccessToken(), 'access-1');
      expect(await storage.readRefreshToken(), 'refresh-1');
    });

    test('leaves the refresh token untouched when none is supplied', () async {
      await storage.saveTokens(
        accessToken: 'access-1',
        refreshToken: 'refresh-1',
      );
      await storage.saveTokens(accessToken: 'access-2');

      expect(await storage.readAccessToken(), 'access-2');
      expect(await storage.readRefreshToken(), 'refresh-1');
    });

    test('clear removes both tokens', () async {
      await storage.saveTokens(
        accessToken: 'access-1',
        refreshToken: 'refresh-1',
      );

      await storage.clear();

      expect(await storage.readAccessToken(), isNull);
      expect(await storage.readRefreshToken(), isNull);
    });

    test('reading an unset token returns null', () async {
      expect(await storage.readAccessToken(), isNull);
    });
  });
}
