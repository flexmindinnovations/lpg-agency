import 'package:device_identity/device_identity.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  group('DeviceIdentity', () {
    test('creates the install ID on first run and saves it', () async {
      final storage = MemoryStorage();

      final identity = await loadIdentity(storage: storage);

      expect(identity.installId, hasLength(64));
      expect(storage.installId, identity.installId);
      expect(storage.installIdWrites, 1);
    });

    test('keeps the same install ID on every later run', () async {
      final storage = MemoryStorage();
      final first = await loadIdentity(storage: storage);

      final second = await loadIdentity(storage: storage);

      expect(second.installId, first.installId);
      expect(storage.installIdWrites, 1);
    });

    test('makes a new install ID when storage was cleared', () async {
      final first = await loadIdentity(storage: MemoryStorage());

      final afterReinstall = await loadIdentity(storage: MemoryStorage());

      expect(afterReinstall.installId, isNot(first.installId));
    });

    test('sends the install ID and app type as headers', () async {
      final identity = await loadIdentity(
        storage: MemoryStorage(installId: 'install-id-0123456789'),
        appType: 'admin_app',
      );

      expect(identity.headers, {
        'X-Device-Id': 'install-id-0123456789',
        'X-App-Type': 'admin_app',
      });
    });

    test('the sign-in body carries the details and no name', () async {
      final identity = await loadIdentity();

      expect(identity.authBody, {
        'manufacturer': 'Xiaomi',
        'model': 'Redmi 12',
        'os_version': 'Android 13',
        'app_version': '1.4.0',
        'platform': 'android',
        'hardware_id': 'android-id-1',
      });
    });

    test('never puts the install ID in the body or in text', () async {
      final identity = await loadIdentity();

      expect(identity.authBody.toString(), isNot(contains(identity.installId)));
      expect(identity.toString(), isNot(contains(identity.installId)));
    });
  });

  group('DeviceDetails.toJson', () {
    test('leaves out what the phone did not report', () {
      expect(const DeviceDetails(model: 'Redmi 12').toJson(), {
        'model': 'Redmi 12',
      });
    });

    test('trims blanks and clips to the lengths the server accepts', () {
      final json = DeviceDetails(
        model: '  ${'m' * 150}  ',
        manufacturer: '   ',
      ).toJson(name: 'n' * 100);

      expect(json.containsKey('manufacturer'), isFalse);
      expect((json['model'] as String).length, 100);
      expect((json['name'] as String).length, 60);
    });
  });
}
