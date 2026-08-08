import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

void main() {
  group('NoopLocalDatabase', () {
    test('opens and closes cleanly', () async {
      final db = NoopLocalDatabase();
      expect(db.isOpen, isFalse);

      await db.open();
      expect(db.isOpen, isTrue);

      await db.close();
      expect(db.isOpen, isFalse);
    });
  });
}
