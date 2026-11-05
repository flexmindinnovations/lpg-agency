import 'dart:math';

import 'package:device_identity/device_identity.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('generateInstallId', () {
    test('is 64 hex characters', () {
      expect(generateInstallId(), matches(RegExp(r'^[0-9a-f]{64}$')));
    });

    test('is random: two calls differ', () {
      expect(generateInstallId(), isNot(generateInstallId()));
    });

    test('is built only from the random source, nothing about the phone', () {
      expect(generateInstallId(Random(1)), generateInstallId(Random(1)));
      expect(generateInstallId(Random(1)), isNot(generateInstallId(Random(2))));
    });

    test('fits the server\'s 16 to 128 character install-ID rule', () {
      expect(generateInstallId().length, inInclusiveRange(16, 128));
    });
  });

  group('SecureDeviceIdentityStorage', () {
    late Map<String, String> store;
    late SecureDeviceIdentityStorage storage;

    setUp(() {
      store = {};
      storage = SecureDeviceIdentityStorage(
        write: (key, value) async => store[key] = value,
        read: (key) async => store[key],
      );
    });

    test('round-trips the install ID and the name', () async {
      await storage.writeInstallId('abc');
      await storage.writeName('Ravi\'s phone');

      expect(await storage.readInstallId(), 'abc');
      expect(await storage.readName(), 'Ravi\'s phone');
    });

    test('keeps them under their own keys', () async {
      await storage.writeInstallId('abc');
      await storage.writeName('Van 2');

      expect(store.keys, containsAll(['device.install_id', 'device.name']));
    });

    test('reads nothing before anything is saved', () async {
      expect(await storage.readInstallId(), isNull);
      expect(await storage.readName(), isNull);
    });
  });
}
